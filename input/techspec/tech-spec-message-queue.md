# Message Queue Tech Spec

## 1. Scope

This spec applies to all business scenarios that use RabbitMQ or Kafka for asynchronous message processing, including event notifications, async tasks, and service decoupling. It covers code under the `mq`, `producer`, and `consumer` packages.

## 2. Key Requirements

### 2.1 Message Naming Rules

- **MUST**: Exchange names must use the format `{domain}.{purpose}.exchange`
- **MUST**: Queue names must use the format `{domain}.{function}.queue`
- **MUST**: Routing keys must use the format `{domain}.{entity}.{operation}`
- **MUST**: Topic names must use the format `{domain}.{entity}.{eventType}`
- **FORBID**: Names must not contain spaces or special characters
- **NORM**: Names should use lowercase letters separated by dots

### 2.2 Message Payload Structure Rules

- **MUST**: Message payloads must use JSON format
- **MUST**: Payloads must include the common fields `messageId`, `timestamp`, `eventType`, and `data`
- **MUST**: Payload size must not exceed 512 KB
- **FORBID**: Payloads must not include sensitive information such as passwords or secrets
- **NORM**: Payload fields should use camelCase naming

### 2.3 Message Production Rules

- **MUST**: Serialize the payload to JSON before sending a message
- **MUST**: Set a message expiration time (TTL)
- **MUST**: Enable message persistence
- **FORBID**: Do not send messages inside a transaction because it can hold transactional resources too long
- **NORM**: Use publisher confirmations to ensure send success
- **NORM**: Retry failed sends with a maximum of 3 attempts

### 2.4 Message Consumption Rules

- **MUST**: Consumer handlers must be idempotent
- **MUST**: Failed messages must be routed to a dead-letter queue
- **MUST**: Consumer exceptions must not result in message loss
- **FORBID**: Consumer handlers must not perform long blocking operations
- **NORM**: Consumer timeout should be set to 30 seconds
- **NORM**: The number of concurrent consumers should match business traffic volume

### 2.5 Exception Handling Rules

- **MUST**: Log consumer exceptions in detail, including message ID and content
- **MUST**: Business-exception messages must enter a dead-letter queue for manual handling
- **MUST**: System-exception messages must be retried
- **NORM**: Retry intervals should use exponential backoff
- **NORM**: Messages exceeding the retry limit should enter a dead-letter queue

### 2.6 Monitoring and Alerting Rules

- **MUST**: Monitor message backlog size
- **MUST**: Monitor consumer failure rate
- **MUST**: Trigger alerts when dead-letter queues contain data
- **NORM**: Record slow logs when processing time exceeds the threshold

## 3. Full Specification Details

### 3.1 Message Naming Examples

| Business Scenario | Exchange | Queue | Routing Key |
|------------------|----------|-------|-------------|
| Order creation | `order.event.exchange` | `order.create.queue` | `order.order.created` |
| User registration | `user.event.exchange` | `user.register.queue` | `user.user.registered` |
| Inventory deduction | `inventory.event.exchange` | `inventory.deduct.queue` | `inventory.stock.deducted` |
| Payment callback | `payment.callback.exchange` | `payment.callback.queue` | `payment.transaction.completed` |

### 3.2 Standard Message Payload Structure

```json
{
    "messageId": "MSG2024010100001",
    "timestamp": 1704067200000,
    "eventType": "ORDER_CREATED",
    "source": "order-service",
    "data": {
        "orderNo": "O2024010100001",
        "userId": "U10001",
        "amount": 99.99
    },
    "traceId": "abc123def456"
}
```

### 3.3 Message TTL Configuration

| Message Type | Expiration | Description |
|-------------|------------|-------------|
| Real-time notification | 5 minutes | For example, order status change notifications |
| Async task | 30 minutes | For example, report generation tasks |
| Batch processing | 2 hours | For example, data synchronization tasks |
| Scheduled message | As needed | For example, delayed order cancellation |

### 3.4 Dead-Letter Queue Configuration

- Dead-letter exchange naming: `{originalExchange}.dlx`
- Dead-letter queue naming: `{originalQueue}.dlq`
- Dead-letter message retention time: 7 days
- Dead-letter queues must be monitored and handled manually

### 3.5 Consumer Concurrency Settings

| Business Type | Consumer Count | Description |
|--------------|----------------|-------------|
| High-frequency messages | 10-20 | For example, log collection and telemetry reporting |
| Medium-frequency messages | 5-10 | For example, order processing and inventory deduction |
| Low-frequency messages | 1-3 | For example, report generation and data archiving |

## 4. Correct Examples

```java
// ✅ Correct Example 1: message constant definitions
public class MqConstants {
    
    // Exchanges
    public static final String ORDER_EVENT_EXCHANGE = "order.event.exchange";
    public static final String USER_EVENT_EXCHANGE = "user.event.exchange";
    
    // Queues
    public static final String ORDER_CREATE_QUEUE = "order.create.queue";
    public static final String USER_REGISTER_QUEUE = "user.register.queue";
    
    // Dead-letter queues
    public static final String ORDER_CREATE_DLQ = "order.create.queue.dlq";
    public static final String USER_REGISTER_DLQ = "user.register.queue.dlq";
    
    // Routing keys
    public static final String ORDER_CREATED_KEY = "order.order.created";
    public static final String USER_REGISTERED_KEY = "user.user.registered";
    
    // Message TTL in milliseconds
    public static final long REALTIME_TTL = 300000;       // 5 minutes
    public static final long ASYNC_TASK_TTL = 1800000;    // 30 minutes
    public static final long BATCH_PROCESS_TTL = 7200000; // 2 hours
}

// ✅ Correct Example 2: message payload definition
@Data
public class MqMessage<T> implements Serializable {
    
    @ApiModelProperty(value = "Message ID")
    private String messageId;
    
    @ApiModelProperty(value = "Message timestamp")
    private Long timestamp;
    
    @ApiModelProperty(value = "Event type")
    private String eventType;
    
    @ApiModelProperty(value = "Source service")
    private String source;
    
    @ApiModelProperty(value = "Trace ID")
    private String traceId;
    
    @ApiModelProperty(value = "Business payload")
    private T data;
    
    public static <T> MqMessage<T> build(String eventType, T data) {
        MqMessage<T> message = new MqMessage<>();
        message.setMessageId(generateMessageId());
        message.setTimestamp(System.currentTimeMillis());
        message.setEventType(eventType);
        message.setSource(SpringApplication.getApplicationName());
        message.setTraceId(TraceUtil.getTraceId());
        message.setData(data);
        return message;
    }
    
    private static String generateMessageId() {
        return "MSG" + DateUtil.format(new Date(), "yyyyMMddHHmmss") + RandomUtil.randomNumbers(6);
    }
}

// ✅ Correct Example 3: message producer
@Component
@Slf4j
public class OrderEventProducer {
    
    @Autowired
    private RabbitTemplate rabbitTemplate;
    
    public void sendOrderCreatedEvent(OrderDTO order) {
        MqMessage<OrderDTO> message = MqMessage.build("ORDER_CREATED", order);
        
        try {
            rabbitTemplate.convertAndSend(
                MqConstants.ORDER_EVENT_EXCHANGE,
                MqConstants.ORDER_CREATED_KEY,
                JSON.toJSONString(message),
                msg -> {
                    // Set message persistence
                    msg.getMessageProperties().setDeliveryMode(MessageDeliveryMode.PERSISTENT);
                    // Set expiration time
                    msg.getMessageProperties().setExpiration(String.valueOf(MqConstants.REALTIME_TTL));
                    // Set message ID
                    msg.getMessageProperties().setMessageId(message.getMessageId());
                    return msg;
                }
            );
            
            EPLogger.info().withDlTag(this.getClass().getName())
                .withMessage("Order-created message sent successfully")
                .with("orderNo", order.getOrderNo())
                .with("messageId", message.getMessageId())
                .flush();
        } catch (Exception e) {
            EPLogger.error().withDlTag(this.getClass().getName())
                .withMessage("Failed to send order-created message")
                .with("orderNo", order.getOrderNo())
                .withException(e)
                .flush();
            throw new GlBasicException("Failed to send order-created message");
        }
    }
}

// ✅ Correct Example 4: message consumer with idempotency
@Component
@RabbitListener(queues = MqConstants.ORDER_CREATE_QUEUE)
public class OrderCreateConsumer {
    
    @Autowired
    private OrderService orderService;
    
    @Autowired
    private MessageProcessLogMapper messageLogMapper;
    
    @RabbitHandler
    public void handleMessage(String messageJson, Channel channel, 
            @Header(AmqpHeaders.DELIVERY_TAG) long deliveryTag) {
        
        MqMessage<OrderDTO> message = null;
        try {
            message = JSON.parseObject(messageJson, new TypeReference<MqMessage<OrderDTO>>() {});
            
            // Idempotency check
            if (isMessageProcessed(message.getMessageId())) {
                EPLogger.info().withDlTag(this.getClass().getName())
                    .withMessage("Message already processed, skipping")
                    .with("messageId", message.getMessageId())
                    .flush();
                channel.basicAck(deliveryTag, false);
                return;
            }
            
            // Execute business logic
            orderService.handleOrderCreatedEvent(message.getData());
            
            // Record success
            recordMessageProcessed(message.getMessageId(), "SUCCESS");
            
            // Acknowledge message
            channel.basicAck(deliveryTag, false);
            
            EPLogger.info().withDlTag(this.getClass().getName())
                .withMessage("Order-created message processed successfully")
                .with("messageId", message.getMessageId())
                .flush();
                
        } catch (BusinessException e) {
            // Business exception -> dead-letter queue
            EPLogger.error().withDlTag(this.getClass().getName())
                .withMessage("Business processing failed for order-created message")
                .with("messageId", message != null ? message.getMessageId() : "unknown")
                .withException(e)
                .flush();
            // Reject without requeueing, send to dead-letter queue
            channel.basicNack(deliveryTag, false, false);
            
        } catch (Exception e) {
            // System exception -> retry by requeueing
            EPLogger.error().withDlTag(this.getClass().getName())
                .withMessage("Unexpected exception while processing order-created message")
                .with("messageId", message != null ? message.getMessageId() : "unknown")
                .withException(e)
                .flush();
            // Reject and requeue
            channel.basicNack(deliveryTag, false, true);
        }
    }
    
    private boolean isMessageProcessed(String messageId) {
        MessageProcessLog log = messageLogMapper.selectByMessageId(messageId);
        return log != null && "SUCCESS".equals(log.getProcessStatus());
    }
    
    private void recordMessageProcessed(String messageId, String status) {
        MessageProcessLog log = new MessageProcessLog();
        log.setMessageId(messageId);
        log.setProcessStatus(status);
        log.setProcessTime(new Date());
        messageLogMapper.insertSelective(log);
    }
}

// ✅ Correct Example 5: RabbitMQ configuration class
@Configuration
public class RabbitMQConfig {
    
    // Order-created exchange
    @Bean
    public DirectExchange orderEventExchange() {
        return new DirectExchange(MqConstants.ORDER_EVENT_EXCHANGE, true, false);
    }
    
    // Order-created queue
    @Bean
    public Queue orderCreateQueue() {
        return QueueBuilder.durable(MqConstants.ORDER_CREATE_QUEUE)
            .withArgument("x-dead-letter-exchange", MqConstants.ORDER_EVENT_EXCHANGE + ".dlx")
            .withArgument("x-dead-letter-routing-key", MqConstants.ORDER_CREATED_KEY + ".dlq")
            .build();
    }
    
    // Order-created dead-letter queue
    @Bean
    public Queue orderCreateDLQ() {
        return QueueBuilder.durable(MqConstants.ORDER_CREATE_DLQ).build();
    }
    
    // Binding
    @Bean
    public Binding orderCreateBinding(Queue orderCreateQueue, DirectExchange orderEventExchange) {
        return BindingBuilder.bind(orderCreateQueue)
            .to(orderEventExchange)
            .with(MqConstants.ORDER_CREATED_KEY);
    }
    
    // Message listener container configuration
    @Bean
    public SimpleRabbitListenerContainerFactory rabbitListenerContainerFactory(
            ConnectionFactory connectionFactory) {
        SimpleRabbitListenerContainerFactory factory = new SimpleRabbitListenerContainerFactory();
        factory.setConnectionFactory(connectionFactory);
        factory.setConcurrentConsumers(5);
        factory.setMaxConcurrentConsumers(10);
        factory.setPrefetchCount(10);
        factory.setAcknowledgeMode(AcknowledgeMode.MANUAL);
        factory.setDefaultRequeueRejected(false);
        return factory;
    }
}

// ✅ Correct Example 6: dead-letter queue alert handling
@Component
@RabbitListener(queues = MqConstants.ORDER_CREATE_DLQ)
public class OrderCreateDLQConsumer {
    
    @Autowired
    private AlertService alertService;
    
    @RabbitHandler
    public void handleDLQMessage(String messageJson, Channel channel,
            @Header(AmqpHeaders.DELIVERY_TAG) long deliveryTag) throws IOException {
        
        EPLogger.warn().withDlTag(this.getClass().getName())
            .withMessage("Message received in dead-letter queue")
            .with("messageContent", messageJson)
            .flush();
        
        // Send alert
        alertService.sendAlert("ORDER_DLQ_ALERT", 
            "An order-created message entered the dead-letter queue and requires manual handling. Message content: " + messageJson);
        
        // Acknowledge message
        channel.basicAck(deliveryTag, false);
    }
}
```

## 5. Incorrect Examples

```java
// ❌ Incorrect 1: non-standard message naming
public class MqConstants {
    // ❌ Uses non-English text
    public static final String EXCHANGE = "order-event-exchange";
    // ❌ Inconsistent naming styles
    public static final String QUEUE1 = "OrderCreateQueue";
    public static final String QUEUE2 = "order_create_queue";
    public static final String QUEUE3 = "orderCreateQueue";
}

// ❌ Incorrect 2: missing common fields in the message payload
@Data
public class OrderMessage {
    // ❌ Contains only business fields, missing message ID, timestamp, event type, and so on
    private String orderNo;
    private String userId;
    private BigDecimal amount;
}

// ❌ Incorrect 3: message without expiration time
@Component
public class OrderEventProducer {
    
    public void sendOrderCreatedEvent(OrderDTO order) {
        rabbitTemplate.convertAndSend(
            MqConstants.ORDER_EVENT_EXCHANGE,
            MqConstants.ORDER_CREATED_KEY,
            JSON.toJSONString(order)
            // ❌ No expiration time set, so messages may accumulate forever
        );
    }
}

// ❌ Incorrect 4: consumer is not idempotent
@Component
@RabbitListener(queues = MqConstants.ORDER_CREATE_QUEUE)
public class OrderCreateConsumer {
    
    @RabbitHandler
    public void handleMessage(String messageJson) {
        MqMessage<OrderDTO> message = JSON.parseObject(messageJson, 
            new TypeReference<MqMessage<OrderDTO>>() {});
        
        // ❌ No processed-message check, which may cause duplicate charging or shipping
        orderService.handleOrderCreatedEvent(message.getData());
    }
}

// ❌ Incorrect 5: bad exception handling that causes message loss
@Component
@RabbitListener(queues = MqConstants.ORDER_CREATE_QUEUE)
public class OrderCreateConsumer {
    
    @RabbitHandler
    public void handleMessage(String messageJson, Channel channel, 
            @Header(AmqpHeaders.DELIVERY_TAG) long deliveryTag) {
        try {
            MqMessage<OrderDTO> message = JSON.parseObject(messageJson, 
                new TypeReference<MqMessage<OrderDTO>>() {});
            orderService.handleOrderCreatedEvent(message.getData());
            channel.basicAck(deliveryTag, false);
        } catch (Exception e) {
            // ❌ Acknowledges even on failure, causing message loss
            channel.basicAck(deliveryTag, false);
            EPLogger.error().withMessage("Processing failed").withException(e).flush();
        }
    }
}

// ✅ Correct approach: reject the message on failure and either requeue or dead-letter it
@Component
@RabbitListener(queues = MqConstants.ORDER_CREATE_QUEUE)
public class OrderCreateConsumer {
    
    @RabbitHandler
    public void handleMessage(String messageJson, Channel channel, 
            @Header(AmqpHeaders.DELIVERY_TAG) long deliveryTag) {
        try {
            MqMessage<OrderDTO> message = JSON.parseObject(messageJson, 
                new TypeReference<MqMessage<OrderDTO>>() {});
            orderService.handleOrderCreatedEvent(message.getData());
            channel.basicAck(deliveryTag, false);
        } catch (Exception e) {
            EPLogger.error().withMessage("Processing failed").withException(e).flush();
            // ✅ Reject without requeueing so it enters the dead-letter queue
            channel.basicNack(deliveryTag, false, false);
        }
    }
}

// ❌ Incorrect 6: sending a message inside a transaction
@Service
public class OrderServiceImpl {
    
    @Transactional
    public void createOrder(OrderDTO orderDTO) {
        Order order = convertToEntity(orderDTO);
        orderMapper.insertSelective(order);
        
        // ❌ Sends the message before transaction commit
        // If the transaction rolls back, the message cannot be recalled
        orderEventProducer.sendOrderCreatedEvent(orderDTO);
    }
}

// ✅ Correct approach: send after commit using transaction synchronization
@Service
public class OrderServiceImpl {
    
    @Autowired
    private ApplicationContext applicationContext;
    
    @Transactional
    public void createOrder(OrderDTO orderDTO) {
        Order order = convertToEntity(orderDTO);
        orderMapper.insertSelective(order);
        
        // ✅ Send only after transaction commit
        TransactionSynchronizationManager.registerSynchronization(
            new TransactionSynchronization() {
                @Override
                public void afterCommit() {
                    applicationContext.getBean(OrderEventProducer.class)
                        .sendOrderCreatedEvent(orderDTO);
                }
            }
        );
    }
}

// ❌ Incorrect 7: long blocking operations inside the consumer
@Component
@RabbitListener(queues = MqConstants.ORDER_CREATE_QUEUE)
public class OrderCreateConsumer {
    
    @RabbitHandler
    public void handleMessage(String messageJson) {
        MqMessage<OrderDTO> message = JSON.parseObject(messageJson, 
            new TypeReference<MqMessage<OrderDTO>>() {});
        
        // ❌ Executes slow tasks in the consumer, blocking other messages
        generateComplexReport(message.getData());
        uploadFileToOSS(message.getData());
        sendEmailNotification(message.getData());
    }
}

// ✅ Correct approach: handle slow tasks asynchronously or in a dedicated queue
@Component
@RabbitListener(queues = MqConstants.ORDER_CREATE_QUEUE)
public class OrderCreateConsumer {
    
    @Autowired
    private AsyncTaskService asyncTaskService;
    
    @RabbitHandler
    public void handleMessage(String messageJson) {
        MqMessage<OrderDTO> message = JSON.parseObject(messageJson, 
            new TypeReference<MqMessage<OrderDTO>>() {});
        
        // Handle core business logic synchronously
        orderService.handleOrderCreatedEvent(message.getData());
        
        // ✅ Handle non-core tasks asynchronously
        asyncTaskService.asyncGenerateReport(message.getData());
        asyncTaskService.asyncSendNotification(message.getData());
    }
}

// ❌ Incorrect 8: oversized message payload
@Data
public class ExportMessage {
    private String taskNo;
    // ❌ Sends too much data directly inside the message
    private List<ExportRowData> allData;  // May contain tens of thousands of rows
    private byte[] fileContent;           // File content placed directly into the message
}

// ✅ Correct approach: send only references in the message
@Data
public class ExportMessage {
    private String taskNo;
    private String dataFileUrl;    // URL of the data file stored in OSS
    private Integer totalCount;    // Total number of records
}

// ❌ Incorrect 9: dead-letter queue is not configured
@Configuration
public class RabbitMQConfig {
    
    @Bean
    public Queue orderCreateQueue() {
        // ❌ No dead-letter queue configured, so failed messages cannot be handled properly
        return QueueBuilder.durable(MqConstants.ORDER_CREATE_QUEUE).build();
    }
}

// ❌ Incorrect 10: unreasonable consumer concurrency configuration
@Configuration
public class RabbitMQConfig {
    
    @Bean
    public SimpleRabbitListenerContainerFactory rabbitListenerContainerFactory(
            ConnectionFactory connectionFactory) {
        SimpleRabbitListenerContainerFactory factory = new SimpleRabbitListenerContainerFactory();
        factory.setConnectionFactory(connectionFactory);
        // ❌ Too many consumers for low-frequency traffic, wasting resources
        factory.setConcurrentConsumers(50);
        factory.setMaxConcurrentConsumers(100);
        return factory;
    }
}
```
