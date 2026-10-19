#set( $dollar = '$' )
#set( $hash = '#' )
${hash} MySQL
MySQL 8.4 使用 mysql-data 命名卷。开发环境通过上级 docker-compose.dev.yml 映射 127.0.0.1:3306，生产不发布端口。conf.d/my.cnf 保持只读、644 权限。

首次空卷启动由官方入口创建业务库 ${databaseName} 与同名用户，随后 source initdb/10-middleware.sh，创建 nacos_config、xxl_job 及独立用户。业务表由 Flyway 管理，中间件表见 ../sql，不包含物理外键。

开发配置示例统一到 ../.env.example；服务器凭据由 prepare 生成。已有卷不重跑初始化，修改 .env 不会轮换数据库密码。自动备份范围仍为业务库，中间件备份见 ../sql/README.md。
