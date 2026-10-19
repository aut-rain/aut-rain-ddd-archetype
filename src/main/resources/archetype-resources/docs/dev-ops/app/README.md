#set( $dollar = '$' )
#set( $hash = '#' )
${hash} 应用部署
以 environment/docker-compose.yml 为第一个 -f 文件，再组合 app/docker-compose.yml，相对路径按 environment 解析，构建上下文 .. 为发布包根目录。

后端 Dockerfile 位于源码 app-backend/${artifactId}-app/Dockerfile，默认读取该模块 target/${artifactId}-app.jar；打包脚本复制到发布包 app/Dockerfile，Compose 通过 JAR_FILE=app.jar 指向发布产物。environment/nginx/Dockerfile 读取 environment/nginx/conf.d/default.conf；静态页面由 WEB_ROOT 只读挂载。生产入口为 ${httpPort}，服务器 HTTP_PORT 可覆盖。

源码没有发布 app.jar，使用 docs/dev-script/deployment 的打包、上传和部署入口；不额外复制一套 start/stop 脚本。
