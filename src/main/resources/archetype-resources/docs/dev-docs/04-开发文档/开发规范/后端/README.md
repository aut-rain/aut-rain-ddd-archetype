#set( $dollar = '$' )
#set( $hash = '#' )
${hash} 后端规范

Java 21，不使用 Lombok。types/api/domain/infrastructure/trigger/app 按职责分层。配置从环境变量读取，异常和输入校验应有统一处理。

领域层只依赖 types，仓储和外部服务使用端口；基础设施层实现端口；接口层通过统一的 `ApiResponse` 返回结果；预期业务失败抛出 `BusinessException`，由接口层统一转换。跨模块依赖必须保持架构文档中的方向。

目录遵循 XFG 标准 DDD 分层：领域使用 `domain/<业务名>/model/{aggregate,entity,valobj}`、`service`、`repository`、`adapter`；持久化实现放在 `infrastructure/persistent`，外部调用放在 `infrastructure/gateway`，Redis 封装放在 `infrastructure/redis`；Controller 和异常处理放在 `trigger/http`，其他入口按 `rpc`、`listener`、`job` 分类。`api/model` 保存契约 DTO，`types/common` 保存跨模块通用常量。

`package-info.java` 表达预留包职责，不添加无行为的 Marker/Placeholder 类来占位。示例领域 `xxx`、`yyy` 应替换为实际名称。中间件按需引入并在 app/config 中装配，避免生成工程一启动就依赖所有中间件。

默认单元测试不监听端口、不连接外部服务。需要数据库或 Redis 的集成测试放入 `test/infrastructure/persistent` 或 `test/infrastructure/redis`，使用 `*IT` 命名，并为其配置显式运行的集成测试流程。
