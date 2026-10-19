#set( $dollar = '$' )
#set( $hash = '#' )
${hash} 后端规范

Java 21，不使用 Lombok。types/api/domain/infrastructure/trigger/app 按职责分层。配置从环境变量读取，异常和输入校验应有统一处理。

领域层只依赖 types，仓储和外部服务使用端口；基础设施层实现端口；接口层通过统一的 `ApiResponse` 返回结果；预期业务失败抛出 `BusinessException`，由接口层统一转换。跨模块依赖必须保持架构文档中的方向。
