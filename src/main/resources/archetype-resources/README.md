#set( $dollar = '$' )
#set( $hash = '#' )
${hash} ${projectName}

由 `com.autrain:aut-rain-ddd-archetype:1.0.0` 生成，目录包含 `app-backend/` 后端、`web/` 前端、`docs/` 文档与部署。`.runtime/`、`logs/` 不预先生成，由打包脚本和日志组件按需创建，其内容不提交。

后端 Maven 聚合入口是 `app-backend/pom.xml`，生成结果默认不需要项目根 `pom.xml`。如果通过 IntelliJ IDEA 的 Archetype 向导创建，IDEA 可能额外留下一个只有坐标信息的临时根 POM；关闭项目后删除该文件，并从 `app-backend/pom.xml` 重新导入 Maven 即可。

本项目是生成后的应用工程。模板维护者应在 Archetype 源码目录执行 `mvn clean install`；不要在生成项目中执行 `create-from-project`。

后端 Maven groupId 为 `com.autrain`，Java 根包为 `com.rain.${artifactId.replace('-', '_')}`，按 `com.rain.<artifactId>` 生成，项目名中的连字符转换为下划线。Maven 坐标与 Java 包名分别遵循这两套命名规则。

${hash}${hash} 构建验证（不启动服务）

```powershell
mvn -f app-backend/pom.xml clean package
corepack pnpm --dir web install --frozen-lockfile
corepack pnpm --dir web typecheck
corepack pnpm --dir web lint
corepack pnpm --dir web test
corepack pnpm --dir web build
```

逐条执行上述命令，任一步失败时先修复再继续。

${hash}${hash} 本地运行（仅在明确需要启动时执行）

Java 21、Maven 3.9+、Node.js 22.22.0、Corepack/pnpm 11.0.8。准备 MySQL 数据库 `${databaseName}`，通过 `APP_DB_URL`、`APP_DB_USERNAME`、`APP_DB_PASSWORD` 配置连接；`.env.example` 仅作参考，Spring 不会自动读取 `.env`。

PowerShell 设置环境变量并完成后端打包后，运行 `java -jar app-backend/${artifactId}-app/target/${artifactId}-app.jar`；前端安装依赖后运行 `corepack pnpm --dir web dev`。MySQL 使用 3306，后端使用 8080，前端使用 5137，开发代理 `/api` 到后端；生产 Nginx 默认对外使用 80（可通过 `httpPort` 调整）。默认没有真实数据库密码。

${hash}${hash} 当前范围

提供六模块 Java 骨架、React 起始页、Flyway 基线、统一响应/异常/校验基础类型、DDD 包结构、构建验证与分层部署工具。不包含具体业务、登录/RBAC 或数据库驱动页面运行目录；这些需要在本项目中继续开发，部署健康检查使用 `/api/v1/ping`。

领域代码按业务边界放在 `domain/<业务领域>/` 下，使用 `model/aggregate`、`model/entity`、`model/valueobject`、`service`、`repository` 和 `adapter` 包。仓储和外部能力先在领域层定义端口，再由 `infrastructure` 实现；`trigger` 只负责入站适配和接口转换。

后端不用 Lombok；数据库不使用物理外键。迁移位于 `app-backend/${artifactId}-app/src/main/resources/db/migration`，已发布版本只能追加，不能修改。

后端配置位于 `app-backend/${artifactId}-app/src/main/resources`：`application.yml` 保存公共配置，`application-dev.yml`、`application-test.yml`、`application-prod.yml` 分别对应开发、测试和生产环境；生产环境必须通过 `APP_DB_URL`、`APP_DB_USERNAME`、`APP_DB_PASSWORD` 提供数据库连接。`banner.txt` 和 `logback-spring.xml` 提供启动标识与控制台/滚动文件日志配置，MyBatis 映射文件放在 `mybatis/mapper`，配置文件放在 `mybatis/config`。

部署入口与各脚本说明见 [部署工具](docs/dev-script/deployment/README.md)。新生成的项目可不初始化 Git 直接构建发布包，此时版本来源记为 unversioned；需要可追踪交付时先提交代码。

运维配置按 docs/dev-ops/app（后端应用）、docs/dev-ops/environment（Nginx 与中间件）分层。配置和用法见 [运维配置](docs/dev-ops/README.md)。

后端 Dockerfile 位于 `app-backend/${artifactId}-app/Dockerfile`，默认使用模块 target 中的 JAR。部署工具会将它复制到发布包 app/Dockerfile 并传入 JAR_FILE=app.jar。

根目录 `.gitignore` 已忽略 IDEA 可能创建的 `/.mvn/` 和 `/pom.xml`；后端 `app-backend/pom.xml` 及各模块 POM 正常纳入版本管理。忽略规则不会删除文件，也不会阻止 IDEA 创建文件。
