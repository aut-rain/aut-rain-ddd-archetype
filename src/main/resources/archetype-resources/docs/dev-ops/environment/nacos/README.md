#set( $dollar = '$' )
#set( $hash = '#' )
${hash} Nacos
2.4.3 standalone + MySQL nacos_config，数据库用户 nacos。配置位于 ../docker-compose.yml，表结构位于 ../sql/nacos.sql。

已开启 NACOS_AUTH_ENABLE。NACOS_AUTH_TOKEN 是至少 32 字节随机数据的标准 Base64；NACOS_AUTH_IDENTITY_VALUE 是独立随机值，服务器 prepare 自动生成。

Nacos 2.4.3 首次需经本机入口或受控 SSH 隧道打开 /nacos，按照初始化提示设置 nacos 管理员密码；模板不预置管理员密码。它与数据库密码、token 是不同凭据。完成初始化后再交给团队访问。

开发客户端使用 127.0.0.1:8848，同时需要 9848；容器客户端使用 nacos:8848。生产不向宿主机发布端口，也不经前端 Nginx 公开代理。模板没有替应用引入 Spring Cloud Alibaba 或配置加载依赖。
