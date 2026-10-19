#set( $dollar = '$' )
#set( $hash = '#' )
${hash} 开发文档

数据库迁移必须使用 Flyway；不得使用物理外键。

后端新增领域能力时，先在 `domain` 中定义业务模型和端口，再由 `infrastructure` 实现技术细节，由 `trigger` 暴露接口。禁止 Controller 直接调用 DAO，也禁止领域层引用基础设施实现。
