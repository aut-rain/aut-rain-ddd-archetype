#set( $dollar = '$' )
#set( $hash = '#' )
${hash} 运维配置

参考 XFG 的 app/environment 分层：app 放后端应用，environment 放 Nginx、中间件及配置。脚本保持在 docs/dev-script/deployment；模板生成不会启动服务。

| 文件 | 用途 |
| --- | --- |
| app/docker-compose.yml | 生产 Java app 和 Nginx；与 environment/docker-compose.yml 合并 |
| ../../app-backend/${artifactId}-app/Dockerfile | 后端模块维护镜像定义；打包时复制到发布包 app/Dockerfile |
| environment/nginx/Dockerfile、conf.d/default.conf | Nginx 镜像、API 同源代理及 SPA 路由 |
| environment/docker-compose.yml | 全部中间件的生产基础定义，不发布宿主机端口 |
| environment/docker-compose.dev.yml | 开发端口覆盖层，绑定 127.0.0.1，项目名 ${artifactId}-dev |
| environment/.env.example | 开发变量示例，复制为 .env 后填入独立随机凭据 |
| environment/mysql/compose.yaml、conf.d/my.cnf | MySQL 服务定义及字符集配置 |
| environment/mysql/initdb/10-middleware.sh | 空卷首次建中间件库、用户、导入 SQL、初始化 XXL-Job 管理员 |
| environment/sql/nacos.sql、xxl-job.sql | 与镜像版本匹配的中间件表结构 |
| environment/redis/redis.conf | Redis AOF、监听及保护模式，密码由环境变量传入 |
| environment/rocketmq/broker.conf | Broker 存储、Topic 策略；广播地址由 Compose 注入 |
| environment/nacos/README.md、xxl-job/README.md | 初始化与连接说明 |
| .dockerignore | 镜像构建白名单 |

${hash}${hash} 本地开发

在项目根目录复制 environment/.env.example 为同目录 .env。按示例生成不同的密码和 Base64 Nacos token，不提交 .env。以下命令供需要启动时手动执行：

```powershell
docker compose --env-file docs/dev-ops/environment/.env -f docs/dev-ops/environment/docker-compose.yml -f docs/dev-ops/environment/docker-compose.dev.yml config --quiet
docker compose --env-file docs/dev-ops/environment/.env -f docs/dev-ops/environment/docker-compose.yml -f docs/dev-ops/environment/docker-compose.dev.yml up -d --wait
docker compose --env-file docs/dev-ops/environment/.env -f docs/dev-ops/environment/docker-compose.yml -f docs/dev-ops/environment/docker-compose.dev.yml ps
```

停止使用相同参数执行 stop；down 保留卷，down -v 删除该项目全部中间件数据，仅在明确清空时使用。up 末尾可指定 mysql redis 等服务；Nacos 和 XXL-Job 的 MySQL 依赖自动启动。

| 服务 | 镜像 | 本机开发端口 | 生产网络地址 |
| --- | --- | --- | --- |
| MySQL | mysql:8.4 | 3306 | mysql:3306 |
| Redis | redis:7.4.2-alpine | 6379 | redis:6379 |
| Nacos | nacos/nacos-server:v2.4.3 | 8848、9848 gRPC | nacos:8848、nacos:9848 |
| RocketMQ | apache/rocketmq:5.3.2 | NameServer 9876、Broker 10909/10911/10912 | rocketmq-namesrv:9876、rocketmq-broker:10911 |
| XXL-Job | xuxueli/xxl-job-admin:2.4.1 | 9090 | xxl-job-admin:9090 |
| Java | 项目构建 | 8080 | app:8080 |
| 前端 | 项目构建 | Vite 5137 | Nginx 对外 ${httpPort}，容器 80 |

Nacos 控制台：http://127.0.0.1:8848/nacos；XXL-Job：http://127.0.0.1:9090/xxl-job-admin。没有附带 Redis Commander、RocketMQ Dashboard 或 phpMyAdmin。

${hash}${hash} 生产部署

使用[部署脚本](../dev-script/deployment/README.md)。发布包保留 app/environment 层次；首次与全量部署启动全部中间件，单端迭代仅更新对应应用，中间件变更须全量迭代。业务后端与中间件连接 middleware 网络，数据库连接 database，Nginx 只连接 frontend。

生产只有 Nginx 发布宿主机端口；管理页面可通过 SSH 隧道转发到服务在服务器上的 bridge IP（docker inspect 查询），如 ssh -L 8848:容器IP:8848 user@server。容器重建后重新查询 IP。Nacos 管理员先在受控隧道中初始化再交给团队访问。

单机配置建议至少 4 CPU / 8 GiB 内存，预留消息和数据库磁盘空间。当前仅提供基础设施，业务 SDK、Nacos 配置加载、XXL-Job 执行器仍需按项目选用。XXL-Job 健康检查只确认监听端口，验收时应实际登录并验证执行器回调。

业务库 ${databaseName} 继续由应用 Flyway 管理；中间件库独立初始化，不接入业务 Flyway。已有数据卷不会重新执行初始化 SQL，不能通过删卷做迭代。备份和已有环境升级见 [SQL 说明](environment/sql/README.md)。
