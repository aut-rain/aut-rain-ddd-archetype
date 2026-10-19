#set( $dollar = '$' )
#set( $hash = '#' )
${hash} RocketMQ
NameServer/Broker 使用官方 apache/rocketmq:5.3.2，单 Master。消息卷 rocketmq-store，日志使用独立命名卷。生产广播 rocketmq-broker，开发广播 127.0.0.1，适用于本机 remoting 客户端；没有 Proxy，不提供 RocketMQ 5 gRPC 接入。

关闭自动 Topic/消费组创建，在 environment 目录显式初始化：

```bash
docker compose --env-file .env -f docker-compose.yml -f docker-compose.dev.yml exec rocketmq-broker sh mqadmin updateTopic -n rocketmq-namesrv:9876 -c DefaultCluster -t example-topic
docker compose --env-file .env -f docker-compose.yml -f docker-compose.dev.yml exec rocketmq-broker sh mqadmin updateSubGroup -n rocketmq-namesrv:9876 -c DefaultCluster -g example-consumer
```

生产使用对应发布目录的 Compose。基础配置未启用 Broker ACL，仅供隔离内部网络；跨主机接入需一并设计广播地址、端口、ACL。只改 NameServer 地址不足以支持外部客户端。
