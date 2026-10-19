#set( $dollar = '$' )
#set( $hash = '#' )
${hash} 中间件初始化 SQL
- nacos.sql 来源：https://github.com/alibaba/nacos/blob/2.4.3/distribution/conf/mysql-schema.sql ，保留 Apache 许可证头。
- xxl-job.sql 来源：https://github.com/xuxueli/xxl-job/blob/2.4.1/doc/db/tables_xxl_job.sql ，保留上游版权说明，移除建库/use、示例执行器/任务和默认密码记录，管理员按 XXL_JOB_ADMIN_PASSWORD 初始化。
- 不复制参考项目的业务分库、历史数据或账号；两套 SQL 均不含物理外键。

mysql/initdb/10-middleware.sh 仅在空卷首次启动时执行。升级镜像须审核并手动应用对应上游升级 SQL，替换初始化文件不会升级已有数据库。业务 Flyway 仅管理 ${databaseName}。

已有部署引入本版前：先备份，保留原 MYSQL_PASSWORD/MYSQL_ROOT_PASSWORD，在服务器 .env 中追加新组件独立凭据。在维护窗口用 root 账号通过标准输入执行初始化脚本中的建库、用户、授权、SOURCE 与 admin INSERT 等效 SQL。目标库和用户应尚不存在；已有中间件库须保留数据及原凭据并按上游迁移，不能重放 CREATE TABLE。不要把密码写入 shell 命令历史。

现有 backup 动作只备份业务库。中间件库需另行 mysqldump --single-transaction --databases nacos_config xxl_job，密码从容器环境读取，输出保存为权限 600 的备份。Redis AOF 与 RocketMQ store 位于独立命名卷，维护窗口需做一致性快照。卸载 --remove-data 会删除当前项目全部中间件数据卷。
