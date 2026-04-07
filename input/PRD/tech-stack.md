# Tech Stack

## Project Info

- **Name**: example-project
- **Type**: Web Application
- **Language**: Java 17 + TypeScript

---

## Backend

| Item | Value |
|------|-------|
| Framework | Spring Boot 3.x |
| Build Tool | Maven |
| ORM | MyBatis-Plus |
| Database | MySQL 8.0 |
| Cache | Redis |
| Auth | Spring Security + JWT |

### Key Dependencies

```xml
<dependencies>
    <dependency>
        <groupId>org.springframework.boot</groupId>
        <artifactId>spring-boot-starter-web</artifactId>
    </dependency>
    <dependency>
        <groupId>com.baomidou</groupId>
        <artifactId>mybatis-plus-boot-starter</artifactId>
    </dependency>
    <dependency>
        <groupId>mysql</groupId>
        <artifactId>mysql-connector-java</artifactId>
    </dependency>
</dependencies>
```

### Package Structure

```
src/main/java/com/example/
├── controller/     # REST API
├── service/        # Business Logic
├── mapper/         # MyBatis Mapper
├── entity/         # Database Entity
├── dto/            # Data Transfer Object
├── config/         # Configuration
└── util/           # Utilities
```

---

## Frontend

| Item | Value |
|------|-------|
| Framework | React 18 |
| Build Tool | Vite |
| UI Library | Ant Design 5.x |
| State | Zustand |
| HTTP | Axios |
| Router | React Router 6 |

### Key Dependencies

```json
{
  "dependencies": {
    "react": "^18.2.0",
    "antd": "^5.12.0",
    "axios": "^1.6.0",
    "zustand": "^4.4.0",
    "react-router-dom": "^6.20.0"
  }
}
```

### Directory Structure

```
src/
├── pages/          # Page Components
├── components/     # Reusable Components
├── api/            # API Calls
├── stores/         # State Management
├── hooks/          # Custom Hooks
├── utils/          # Utilities
└── types/          # TypeScript Types
```

---

## Build Commands

| Command | Description |
|---------|-------------|
| `mvn clean install` | Build backend |
| `mvn test` | Run backend tests |
| `npm run dev` | Start frontend dev server |
| `npm run build` | Build frontend for production |

---

## Code Style

- **Java**: Google Java Style (Checkstyle)
- **TypeScript**: ESLint + Prettier
- **Max Line Length**: 120

---

## Notes

- Backend runs on port 8080
- Frontend runs on port 5173 (dev) / 3000 (prod)
- API prefix: `/api/v1`