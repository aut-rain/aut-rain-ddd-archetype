#set( $dollar = '$' )
#set( $hash = '#' )
${hash} 架构文档

记录模块边界、调用关系、接口约定及数据流。

## 后端模块边界

```text
app             启动、配置和模块装配
trigger         HTTP、消息、任务等入站适配器
api             对外契约和 DTO
domain          聚合、实体、值对象、领域服务和端口
infrastructure 端口实现、持久化和外部系统适配
types           跨模块的响应、异常和校验基础类型
```

依赖方向遵循：`trigger -> domain -> types`，`infrastructure -> domain -> types`，`api -> types`。
`domain` 只声明仓储与外部能力接口，不能依赖 `infrastructure`；`trigger` 不能绕过领域层直接访问基础设施；`app` 负责装配，不承载业务规则。

领域代码按业务边界放在 `domain/<业务领域>/` 下；聚合根放在 `model/aggregate`，实体放在 `model/entity`，值对象放在 `model/valueobject`，仓储端口放在 `repository`，外部能力端口放在 `adapter`。
