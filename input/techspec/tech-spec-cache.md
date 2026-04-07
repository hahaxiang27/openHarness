# Cache Tech Spec

## 1. Scope

This spec applies to all business scenarios that use Redis as a cache, including data caching, session management, distributed locks, and related cache configuration under the `cache` and `config` packages.

## 2. Key Requirements

### 2.1 Cache Key Naming Rules

- **MUST**: Cache keys must use the format `{module}:{entity}:{operation}:{identifier}`
- **MUST**: Cache keys must use lowercase letters only
- **MUST**: Multiple words must be separated by colons
- **FORBID**: Cache keys must not contain spaces or special characters
- **NORM**: Cache key length should not exceed 128 characters

### 2.2 Cache Expiration Rules

- **MUST**: Every cache entry must have an expiration time
- **MUST**: Expiration time must use seconds as the unit
- **FORBID**: Permanent cache expiration is not allowed unless explicitly approved by an architect for a special case
- **NORM**: High-frequency data should expire in 5-15 minutes
- **NORM**: Low-frequency data should expire in 30 minutes to 2 hours
- **NORM**: Configuration data should expire in 1-6 hours

### 2.3 Cache Data Format Rules

- **MUST**: Cached data must be serialized in JSON format
- **MUST**: Cached objects must implement the `Serializable` interface
- **FORBID**: Do not store raw Java object references in the cache
- **NORM**: Cached data size should not exceed 1 MB
- **NORM**: Data larger than 1 MB should use sharding or another storage strategy

### 2.4 Cache Update Strategy Rules

- **MUST**: Related cache entries must be invalidated whenever data is updated
- **MUST**: Update the database first, then delete the cache
- **FORBID**: Do not delete the cache before updating the database, because it may cause cache penetration or stale-read race conditions
- **NORM**: Use the Cache Aside Pattern
- **NORM**: Log and alert when cache updates fail

### 2.5 Cache Penetration Protection Rules

- **MUST**: When a cache lookup misses, use a mutex lock to prevent cache breakdown
- **MUST**: Cache null-value results as well, using a short expiration time such as 5 minutes
- **NORM**: Use a Bloom filter to block obviously nonexistent keys
- **NORM**: Validate parameters before hitting the cache to filter clearly invalid requests

### 2.6 Exception Handling Rules

- **MUST**: Cache operation failures must not break the main business flow
- **MUST**: If cache reads fail, degrade gracefully by querying the database
- **NORM**: Log errors when cache writes fail
- **NORM**: Add a circuit breaker when the cache service is unavailable

## 3. Full Specification Details

### 3.1 Cache Key Naming Examples

| Business Scenario | Cache Key Format | Example |
|------------------|------------------|---------|
| User information | `user:info:{userId}` | `user:info:U10001` |
| Configuration item | `config:item:{configCode}` | `config:item:SYS001` |
| List data | `{module}:list:{condition}` | `order:list:status:pending` |
| Counter | `{module}:count:{key}` | `login:count:U10001:20240101` |
| Distributed lock | `lock:{resource}:{id}` | `lock:order:O10001` |

### 3.2 Common Expiration Settings

| Data Type | Expiration | Description |
|----------|------------|-------------|
| User session | 30 minutes | Session timeout |
| High-frequency query data | 5 minutes | For example, homepage statistics |
| Business configuration | 2 hours | For example, system parameter configuration |
| Dictionary data | 6 hours | For example, status-code mappings |
| Temporary token | 10 minutes | For example, verification codes |

### 3.3 Cache Read Flow

```
1. Query the cache
2. Cache hit -> return cached data
3. Cache miss -> acquire mutex lock
4. Lock acquired -> query database -> write cache -> release lock -> return data
5. Lock acquisition failed -> retry later or return a default value
```

### 3.4 Cache Update Flow

```
1. Start update
2. Update the database record
3. Database update succeeds -> delete cache
4. Database update fails -> throw exception and do not touch cache
5. Cache deletion fails -> log it and keep business flow unaffected
6. Update complete
```

### 3.5 RedisTemplate Configuration Rules

- Use `StringRedisSerializer` for key serialization
- Use `Jackson2JsonRedisSerializer` for value serialization
- Configure the connection pool with max idle 10 and min idle 2

## 4. Correct Examples

```java
// ✅ Correct Example 1: cache key constant definitions
public class CacheKeyConstants {
    
    public static final String USER_INFO_PREFIX = "user:info:";
    public static final String CONFIG_ITEM_PREFIX = "config:item:";
    public static final String ORDER_LIST_PREFIX = "order:list:";
    public static final String DISTRIBUTED_LOCK_PREFIX = "lock:";
    
    public static String buildUserKey(String userId) {
        return USER_INFO_PREFIX + userId;
    }
    
    public static String buildConfigKey(String configCode) {
        return CONFIG_ITEM_PREFIX + configCode;
    }
}

// ✅ Correct Example 2: query method with caching
@Service
public class UserInfoServiceImpl implements UserInfoService {
    
    @Autowired
    private UserInfoMapper userInfoMapper;
    
    @Autowired
    private RedisTemplate<String, String> redisTemplate;
    
    @Override
    public UserInfoDTO getUserById(String userId) {
        // Query cache
        String cacheKey = CacheKeyConstants.buildUserKey(userId);
        String cachedData = redisTemplate.opsForValue().get(cacheKey);
        
        if (StringUtils.isNotBlank(cachedData)) {
            return JSON.parseObject(cachedData, UserInfoDTO.class);
        }
        
        // Cache miss, query database
        UserInfo userInfo = userInfoMapper.selectByUserId(userId);
        if (userInfo == null) {
            // Cache null value to prevent cache penetration
            redisTemplate.opsForValue().set(cacheKey, "", 5, TimeUnit.MINUTES);
            return null;
        }
        
        // Write cache
        UserInfoDTO dto = convertToDTO(userInfo);
        redisTemplate.opsForValue().set(cacheKey, JSON.toJSONString(dto), 30, TimeUnit.MINUTES);
        
        return dto;
    }
}

// ✅ Correct Example 3: invalidate cache after data update
@Service
public class UserInfoServiceImpl implements UserInfoService {
    
    @Override
    @Transactional(rollbackFor = Exception.class)
    public void updateUserInfo(UserInfoUpdateDTO updateDTO) {
        // Update database first
        UserInfo userInfo = convertToEntity(updateDTO);
        userInfo.setLastModifyDate(new Date());
        int updateCount = userInfoMapper.updateWithOptimisticLock(userInfo);
        
        if (updateCount == 0) {
            throw new GlBasicException("The data was modified by another user. Please refresh and retry");
        }
        
        // Delete cache afterward
        try {
            String cacheKey = CacheKeyConstants.buildUserKey(updateDTO.getUserId());
            redisTemplate.delete(cacheKey);
        } catch (Exception e) {
            EPLogger.error().withDlTag(this.getClass().getName())
                .withMessage("Failed to delete cache").with("userId", updateDTO.getUserId())
                .withException(e).flush();
        }
    }
}

// ✅ Correct Example 4: mutex lock implementation to prevent cache breakdown
@Service
public class ConfigServiceImpl implements ConfigService {
    
    @Override
    public ConfigItemDTO getConfigByCode(String configCode) {
        String cacheKey = CacheKeyConstants.buildConfigKey(configCode);
        
        // Query cache
        String cachedData = redisTemplate.opsForValue().get(cacheKey);
        if (StringUtils.isNotBlank(cachedData)) {
            return JSON.parseObject(cachedData, ConfigItemDTO.class);
        }
        
        // Acquire mutex lock
        String lockKey = CacheKeyConstants.DISTRIBUTED_LOCK_PREFIX + "config:" + configCode;
        boolean locked = tryLock(lockKey, 10);
        
        if (locked) {
            try {
                // Double check
                cachedData = redisTemplate.opsForValue().get(cacheKey);
                if (StringUtils.isNotBlank(cachedData)) {
                    return JSON.parseObject(cachedData, ConfigItemDTO.class);
                }
                
                // Query database
                ConfigItem configItem = configMapper.selectByCode(configCode);
                ConfigItemDTO dto = convertToDTO(configItem);
                
                // Write cache
                redisTemplate.opsForValue().set(cacheKey, JSON.toJSONString(dto), 2, TimeUnit.HOURS);
                
                return dto;
            } finally {
                unlock(lockKey);
            }
        } else {
            // Retry after lock acquisition failure
            try {
                Thread.sleep(50);
                return getConfigByCode(configCode);
            } catch (InterruptedException e) {
                Thread.currentThread().interrupt();
                return null;
            }
        }
    }
    
    private boolean tryLock(String key, int expireSeconds) {
        return redisTemplate.opsForValue().setIfAbsent(key, "1", expireSeconds, TimeUnit.SECONDS);
    }
    
    private void unlock(String key) {
        redisTemplate.delete(key);
    }
}

// ✅ Correct Example 5: graceful degradation for cache failures
@Service
public class OrderStatisticsServiceImpl implements OrderStatisticsService {
    
    @Override
    public OrderStatisticsDTO getTodayStatistics() {
        String cacheKey = "order:statistics:today";
        
        try {
            String cachedData = redisTemplate.opsForValue().get(cacheKey);
            if (StringUtils.isNotBlank(cachedData)) {
                return JSON.parseObject(cachedData, OrderStatisticsDTO.class);
            }
        } catch (Exception e) {
            // Cache read failed, degrade to database query
            EPLogger.warn().withDlTag(this.getClass().getName())
                .withMessage("Cache read failed, degrading to database query")
                .withException(e).flush();
        }
        
        // Query database
        OrderStatisticsDTO statistics = orderMapper.queryTodayStatistics();
        
        // Try writing cache
        try {
            redisTemplate.opsForValue().set(cacheKey, JSON.toJSONString(statistics), 5, TimeUnit.MINUTES);
        } catch (Exception e) {
            EPLogger.warn().withDlTag(this.getClass().getName())
                .withMessage("Cache write failed")
                .withException(e).flush();
        }
        
        return statistics;
    }
}
```

## 5. Incorrect Examples

```java
// ❌ Incorrect 1: non-standard cache key naming
@Service
public class UserServiceImpl {
    
    public UserInfoDTO getUserById(String userId) {
        // ❌ Cache key uses special characters and inconsistent capitalization
        String cacheKey = "UserInfo_" + userId + "_DATA";
        // ❌ Cache key uses non-English text
        String cacheKey2 = "user-info:" + userId;
        // ...
    }
}

// ❌ Incorrect 2: cache entry without expiration
@Service
public class ConfigServiceImpl {
    
    public void saveConfig(ConfigItemDTO dto) {
        String cacheKey = CacheKeyConstants.buildConfigKey(dto.getCode());
        // ❌ No expiration time set, which may lead to memory leaks
        redisTemplate.opsForValue().set(cacheKey, JSON.toJSONString(dto));
    }
}

// ❌ Incorrect 3: deleting cache before updating the database
@Service
public class UserInfoServiceImpl {
    
    @Transactional
    public void updateUserInfo(UserInfoUpdateDTO dto) {
        String cacheKey = CacheKeyConstants.buildUserKey(dto.getUserId());
        // ❌ Delete cache first
        redisTemplate.delete(cacheKey);
        // ❌ Then update the database, which can cause race issues under concurrency
        UserInfo userInfo = convertToEntity(dto);
        userInfoMapper.updateWithOptimisticLock(userInfo);
    }
}

// ❌ Incorrect 4: cache failure breaks the main business flow
@Service
public class OrderServiceImpl {
    
    @Transactional
    public void createOrder(OrderDTO orderDTO) {
        // Create order
        Order order = convertToEntity(orderDTO);
        orderMapper.insertSelective(order);
        
        // ❌ Cache exception is thrown directly, causing transaction rollback
        String cacheKey = "order:info:" + order.getOrderNo();
        redisTemplate.opsForValue().set(cacheKey, JSON.toJSONString(order), 30, TimeUnit.MINUTES);
        // If Redis is unavailable, the entire order creation fails
    }
}

// ✅ Correct approach: cache exceptions must not affect the main business flow
@Service
public class OrderServiceImpl {
    
    @Transactional
    public void createOrder(OrderDTO orderDTO) {
        Order order = convertToEntity(orderDTO);
        orderMapper.insertSelective(order);
        
        try {
            String cacheKey = "order:info:" + order.getOrderNo();
            redisTemplate.opsForValue().set(cacheKey, JSON.toJSONString(order), 30, TimeUnit.MINUTES);
        } catch (Exception e) {
            EPLogger.warn().withDlTag(this.getClass().getName())
                .withMessage("Failed to write order cache").with("orderNo", order.getOrderNo())
                .withException(e).flush();
        }
    }
}

// ❌ Incorrect 5: cache penetration because null values are not cached
@Service
public class UserInfoServiceImpl {
    
    public UserInfoDTO getUserById(String userId) {
        String cacheKey = CacheKeyConstants.buildUserKey(userId);
        String cachedData = redisTemplate.opsForValue().get(cacheKey);
        
        if (StringUtils.isNotBlank(cachedData)) {
            return JSON.parseObject(cachedData, UserInfoDTO.class);
        }
        
        UserInfo userInfo = userInfoMapper.selectByUserId(userId);
        if (userInfo == null) {
            // ❌ No null-value caching, so every request hits the database
            return null;
        }
        
        UserInfoDTO dto = convertToDTO(userInfo);
        redisTemplate.opsForValue().set(cacheKey, JSON.toJSONString(dto), 30, TimeUnit.MINUTES);
        return dto;
    }
}

// ❌ Incorrect 6: cache breakdown because no mutex lock is used
@Service
public class HotConfigServiceImpl {
    
    public HotConfigDTO getHotConfig(String configCode) {
        String cacheKey = "config:hot:" + configCode;
        String cachedData = redisTemplate.opsForValue().get(cacheKey);
        
        if (StringUtils.isNotBlank(cachedData)) {
            return JSON.parseObject(cachedData, HotConfigDTO.class);
        }
        
        // ❌ When the cache expires, many requests may hit the database at once
        HotConfigDTO config = configMapper.selectHotConfig(configCode);
        redisTemplate.opsForValue().set(cacheKey, JSON.toJSONString(config), 10, TimeUnit.MINUTES);
        return config;
    }
}

// ❌ Incorrect 7: cache serialization issue
@Service
public class UserServiceImpl {
    
    public void cacheUser(UserInfo userInfo) {
        String cacheKey = CacheKeyConstants.buildUserKey(userInfo.getUserId());
        // ❌ Storing a Java object directly instead of serializing it to JSON
        redisTemplate.opsForValue().set(cacheKey, userInfo, 30, TimeUnit.MINUTES);
        // This may cause serialization problems or unreadable data
    }
}

// ❌ Incorrect 8: inconsistent cache key composition
@Service
public class OrderServiceImpl {
    
    public OrderDTO getOrder(String orderNo) {
        // ❌ Different methods use different key composition styles
        String cacheKey1 = "order:" + orderNo;
        String cacheKey2 = "order:info:" + orderNo;
        String cacheKey3 = "order_info_" + orderNo;
        // This causes cache misses and inconsistency
    }
}

// ❌ Incorrect 9: cache avalanche caused by identical expiration times
@Service
public class ProductServiceImpl {
    
    @PostConstruct
    public void initCache() {
        List<Product> products = productMapper.selectAll();
        for (Product product : products) {
            String cacheKey = "product:info:" + product.getCode();
            // ❌ All items share the same expiration time, causing simultaneous invalidation
            redisTemplate.opsForValue().set(cacheKey, JSON.toJSONString(product), 30, TimeUnit.MINUTES);
        }
    }
}

// ✅ Correct approach: add random jitter to expiration
@Service
public class ProductServiceImpl {
    
    @PostConstruct
    public void initCache() {
        Random random = new Random();
        List<Product> products = productMapper.selectAll();
        for (Product product : products) {
            String cacheKey = "product:info:" + product.getCode();
            int baseTime = 30;
            int randomOffset = random.nextInt(10);
            // ✅ Randomize expiration between 30 and 39 minutes
            redisTemplate.opsForValue().set(cacheKey, JSON.toJSONString(product), 
                baseTime + randomOffset, TimeUnit.MINUTES);
        }
    }
}
```
