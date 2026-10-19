# aut-rain-ddd-archetype

坐标：`com.autrain:aut-rain-ddd-archetype:1.0.0`。这是一个通用的 Java + React DDD 工程模板，当前是可生成、构建和打包的第一版工程骨架。

## 安装到本机 Maven 仓库

将下方示例路径替换为模板实际所在目录。

```powershell
cd D:\workspace\aut-rain-ddd-archetype
mvn -B -ntp clean install
```

此命令构建脚手架并注册本地目录，没有发布到远程 Maven 仓库。

不要对本目录执行 `maven-archetype-plugin:create-from-project`。该命令用于从普通 Maven 项目重新提取 Archetype；本目录已经是整理完成的 Archetype 工程，直接执行 `install` 即可。

## 在 IntelliJ IDEA 中使用

IDEA 必须使用与安装模板相同的 Maven 本地仓库。可以在 IDEA 的 Maven 设置中选择 Maven 发行版和本地仓库，也可以在 IDEA 使用的 Maven 中执行上面的 `mvn clean install`。然后新建 Maven 项目，勾选 **Create from archetype**，添加：

```text
GroupId：    com.autrain
ArtifactId： aut-rain-ddd-archetype
Version：    1.0.0
```

如果 IDEA 使用 `C:\Users\<用户名>\.m2\repository`，模板也必须用该 Maven 配置安装；如果公司镜像要求 `settings.xml`，请在 IDEA 的 Maven User settings file 中选择一个真实存在的文件。不要在模板目录中提交个人 `settings.xml`。

新项目的 `groupId` 建议填写 `com.autrain`，`package` 保持默认 `com.rain` 即可。生成的后端 POM 固定使用 `com.autrain`；Java 包名由模板内部按 `com.rain.<artifactId>` 计算，项目名中的连字符转为下划线，例如 `order-system` 对应 `com.rain.order_system`。这些结果不受 IDEA 向导传入的 `groupId`、`package` 值影响；Java 保留字不能作为项目名。

IDEA 会把元数据中的默认值原样作为 `-D` 参数传递，因此 `package` 默认值不再包含动态表达式。模板也兼容旧向导缓存的表达式和裸 `-Dpackage`，不会将它们用于 Java 文件内容或源码目录。更新模板后建议重新打开创建向导；已生成的项目不会自动修改。

IDEA 的 Maven 项目向导可能会在目标目录中先创建一个只有 `groupId`、`artifactId` 和 `version` 的临时根 `pom.xml`，并在 Archetype 后处理完成后继续保留它。这个文件不是模板中的业务工程 POM；真正的后端 Maven 聚合入口是 `app-backend/pom.xml`。如果要求生成目录完全不含根 POM，请关闭该项目后删除这个临时文件，再用 `app-backend/pom.xml` 作为 Maven 项目导入。更稳定的方式是先按下方命令在一个不存在的目标目录生成，再在 IDEA 中打开生成后的目录，并手动导入 `app-backend/pom.xml`。

## 创建项目

在希望存放新项目的父目录运行。目标项目目录应不存在，不在已有项目上覆盖生成。

```powershell
mvn -B -ntp org.apache.maven.plugins:maven-archetype-plugin:3.4.1:generate `
  '-DarchetypeCatalog=local' `
  '-DarchetypeGroupId=com.autrain' `
  '-DarchetypeArtifactId=aut-rain-ddd-archetype' `
  '-DarchetypeVersion=1.0.0' `
  '-DgroupId=com.autrain' `
  '-DartifactId=order-system' `
  '-Dversion=0.1.0-SNAPSHOT' `
  '-DprojectName=Order System' `
  '-DdatabaseName=order_system' `
  '-DhttpPort=80' `
  '-DinteractiveMode=false'
```

PowerShell 中完整引用每个 `-D` 参数，避免包含点号的坐标被拆分。Linux Bash 使用相同参数，用反斜杠续行代替 PowerShell 反引号。

| 参数 | 用途 / 约束 |
| --- | --- |
| groupId | 向导兼容参数，建议 com.autrain；生成的后端 POM 固定为 com.autrain |
| artifactId | 项目目录、模块前缀、镜像及部署身份；2–40 位小写字母、数字、连字符，字母开头 |
| version | 后端 Maven 版本，例如 0.1.0-SNAPSHOT |
| package | 向导兼容参数，默认 com.rain；实际 Java 包名始终按 com.rain.<artifactId> 计算，连字符转为下划线 |
| projectName | 显示名称，默认 artifactId；第一版支持英文、数字、空格、下划线及连字符 |
| databaseName | 默认 app_db；1–48 位小写字母、数字、下划线，字母开头；不同项目应显式分配不同库名 |
| httpPort | 生产 HTTP 端口，默认 80，范围 1–65535；后端容器端口固定为 8080 |

前端 npm 版本独立初始化为 0.1.0，不套用可能不符合 npm 规则的 Maven 版本。

## 生成目录

```text
order-system/
├── app-backend/
│   ├── pom.xml
│   ├── order-system-types/
│   ├── order-system-api/
│   ├── order-system-domain/
│   ├── order-system-infrastructure/
│   ├── order-system-trigger/
│   └── order-system-app/
├── web/
├── docs/
│   ├── dev-docs/
│   │   ├── 01-产品需求文档/
│   │   ├── 02-UI设计/
│   │   ├── 03-架构文档/
│   │   ├── 04-开发文档/
│   │   └── 05-部署文档/
│   ├── dev-ops/
│   └── dev-script/deployment/
├── .env.example
├── .editorconfig
├── .gitattributes
├── .gitignore
└── README.md
```

`.runtime/` 和 `logs/` 不在生成时预建，分别由打包脚本和日志组件按需创建。生成项目的 `.gitignore` 忽略 IDEA 额外创建的根目录 `/.mvn/` 和 `/pom.xml`，不影响后端模块的 POM。

Maven 聚合入口保持在 `app-backend/pom.xml`。Archetype 生成过程中需要临时根 POM，post-generation hook 会删除由 Maven Archetype 生成的临时根 POM，并恢复 `.gitignore` 文件名；IDEA 自己预创建或重新写入的临时 POM 需要按上一节处理。

`app-backend` 内部参考 XFG 标准 DDD 模板：领域按 `xxx/yyy` 业务包划分，值对象使用 `valobj`；基础设施分为 `persistent`、`gateway`、`redis`，入口分为 `http`、`rpc`、`listener`、`job`，并提供 `api/model`、`app/config`、`types/common` 和分层测试目录。详细结构见 [后端模板说明](src/main/resources/archetype-resources/app-backend/README.md)。包职责通过 `package-info.java` 记录，具体中间件客户端和业务功能按需实现。

## 已提供的能力

- Java 21 / Spring Boot 3.5.11 六模块骨架，不使用 Lombok；提供 `/api/v1/ping` 和 Actuator 健康接口。
- React / TypeScript / Ant Design，Node.js 22.22.0、pnpm 11.0.8，包含锁文件、ESLint、Vitest 和起始页面。
- MySQL / Flyway，初始 V1 为无业务表的基线标记；数据库不使用物理外键，关联由后端逻辑与唯一约束保证。
- 中间件参考 XFG 的 app/environment 分层，提供 MySQL、Redis、Nacos、RocketMQ NameServer/Broker、XXL-Job Compose 与初始化 SQL。
- 分层部署工具：检查、准备/打包/上传、首次与单端/全量迭代、健康检查、监控和卸载。
- 后端 `/opt/<artifactId>`、前端 `/var/www/<artifactId>`，独立 Compose 项目及数据库卷；MySQL 默认 3306、后端 8080、前端开发端口 5137，生产 Nginx 默认对外端口 80，可由 httpPort 指定。
- 开发规范、数据库设计、部署步骤和维护文档目录。

第一版没有包含具体业务、RBAC、登录或数据库驱动页面运行目录；本版重点提供通用 Archetype 的生成与交付链路。

## 验证生成结果

```powershell
python scripts/verify.py
```

需要 Python 3.12+ 和上述 Java/Node 工具链。该命令安装本地 Archetype、生成多组参数的项目，检查目录和模板变量，构建后端、执行前端类型/ESLint/Vitest/生产构建、运行部署工具测试并校验发布包。结果保留在 `target/verification-*/`，便于查看。

使用 `python scripts/verify.py --backend-only` 可只验证生成参数、项目结构及后端构建；包含命令行默认值、IDEA 原样传入表达式、裸 package 参数及非法项目名的回归检查。可用 `--maven "<IDEA 安装目录>/plugins/maven-plugin/lib/maven3/bin/mvn.cmd"` 指定 IDEA 自带 Maven。

验证不启动前后端、数据库或 Docker 服务，不连接部署服务器。实际数据库迁移、镜像构建与服务器部署需要另行验证。

## 维护模板

- 元数据：`src/main/resources/META-INF/maven/archetype-metadata.xml`。
- 模板：`src/main/resources/archetype-resources/`。
- 生成后处理：`src/main/resources/META-INF/archetype-post-generate.groovy`。
- 模块目录使用 `__artifactId__`；Java 内容直接由 artifactId 计算包名。源码暂存在固定目录 `com/rain/project_template`，生成后处理将其改为 `com/rain/<规范化的 artifactId>`，不依赖 Maven 的 packageInPathFormat。
- Maven/Spring/Compose/Bash/PowerShell 自身的美元符号用 `${dollar}`，井号用 `${hash}`，避免被 Velocity 提前解析。每个过滤模板文件头声明这两个变量。
- 修改模板后重新安装并运行生成验证。脚手架升级不会自动修改以前生成的项目。
- 当前仅落地本地文件，未初始化独立 Git 仓库或提交。

## 贡献者

- [zzy（项目负责人）](https://github.com/aut-rain)

## 开源协议

本项目采用 [MIT License](LICENSE)，版权所有 © 2026 zzy。

MIT 协议声明用于脚手架本身。生成模板不附带项目级 LICENSE 文件，也不自动设置生成项目的 Maven/npm 协议声明；生成项目的协议由使用者自行决定。随附第三方文件的原有版权与许可声明保留。
