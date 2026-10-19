#set( $dollar = '$' )
#set( $hash = '#' )
${hash} 后端目录结构

后端以本目录的 `pom.xml` 为 Maven 聚合入口，按 XFG 标准 DDD 模板组织六个模块。Maven groupId 为 `com.autrain`，Java 根包为 `com.rain.${artifactId.replace('-', '_')}`。

下图的 `<base>` 表示 Java 根包对应的目录，所有业务代码位于各模块的 `src/main/java/<base>/` 下。

```text
app-backend/
├── pom.xml
├── ${artifactId}-app/
│   ├── Dockerfile
│   └── src/
│       ├── main/
│       │   ├── java/<base>/
│       │   │   ├── Application.java
│       │   │   └── config/
│       │   └── resources/
│       │       ├── application.yml
│       │       ├── application-dev.yml
│       │       ├── application-test.yml
│       │       ├── application-prod.yml
│       │       ├── banner.txt
│       │       ├── logback-spring.xml
│       │       ├── db/migration/
│       │       └── mybatis/
│       │           ├── config/
│       │           └── mapper/
│       └── test/java/<base>/test/
│           ├── trigger/http/HealthControllerTest.java
│           └── infrastructure/
│               ├── persistent/
│               └── redis/
├── ${artifactId}-api/src/main/java/<base>/api/
│   └── model/
├── ${artifactId}-domain/src/main/java/<base>/domain/
│   ├── xxx/
│   │   ├── model/
│   │   │   ├── aggregate/
│   │   │   ├── entity/
│   │   │   └── valobj/
│   │   ├── service/
│   │   ├── repository/
│   │   └── adapter/
│   └── yyy/                      与 xxx 相同的领域分层
├── ${artifactId}-infrastructure/src/main/java/<base>/infrastructure/
│   ├── persistent/
│   │   ├── dao/
│   │   ├── po/
│   │   └── repository/
│   ├── gateway/
│   │   ├── api/
│   │   ├── dto/
│   │   └── adapter/
│   └── redis/
├── ${artifactId}-trigger/src/main/java/<base>/trigger/
│   ├── http/
│   │   ├── HealthController.java
│   │   └── ApiExceptionHandler.java
│   ├── rpc/
│   ├── listener/
│   └── job/
└── ${artifactId}-types/src/main/java/<base>/types/
    ├── common/
    ├── model/ApiResponse.java
    ├── exception/BusinessException.java
    └── validation/ValidationUtils.java
```

${hash}${hash} 放置规则

| 位置 | 职责 |
| --- | --- |
| app/config | Spring 配置及模块装配，集中配置数据库、缓存、消息等组件 |
| api、api/model | 对外服务接口及其 DTO，供调用方依赖和 trigger/rpc 实现 |
| domain/xxx、domain/yyy | 示例业务领域；开发时改为实际领域名称，每个领域独立组织模型、服务和端口 |
| domain/*/model/valobj | 值对象，沿用 XFG 的 valobj 命名 |
| domain/*/repository | 仓储接口，只描述业务需要的读写能力 |
| domain/*/adapter | 外部能力接口，隔离远程系统协议 |
| infrastructure/persistent | DAO、PO、仓储实现和模型转换 |
| infrastructure/gateway | 外部客户端接口、DTO 及领域适配器实现 |
| infrastructure/redis | 缓存及 Redis 数据访问封装 |
| trigger/http、rpc、listener、job | HTTP、RPC、消息和任务入口，调用领域服务 |
| types/common | 真正跨模块的常量；领域专属常量属于各自领域 |
| app/src/test/java/.../test | 对应层的测试，外部服务集成测试需要显式配置和执行 |

预留包通过 `package-info.java` 说明职责并保留目录，按需添加实现类。RPC、Redis、消息监听和调度目录仅提供组织方式，尚未接入对应 SDK。通用模板不包含用户订单等示例业务，也不默认启用分库分表。

${hash}${hash} 依赖与构建

模块依赖：`api -> types`、`domain -> types`、`infrastructure -> domain`、`trigger -> api/domain/types`、`app -> trigger/infrastructure`。领域层不能依赖基础设施，入口层不能直接调用 DAO；启动类位于根包，覆盖各模块的组件扫描范围。

在项目根目录执行 `mvn -f app-backend/pom.xml clean package`，生成的可执行 JAR 位于 `${artifactId}-app/target/${artifactId}-app.jar`。HTTP 测试通过 MockMvc 在内存中验证接口及异常响应，不启动监听端口、不连接数据库。

Dockerfile 位于 app 模块，部署脚本继续从该模块读取 JAR 和 Dockerfile。数据库变更仍放在 app 的 `db/migration` 下，后端不使用 Lombok，数据库不使用物理外键。
