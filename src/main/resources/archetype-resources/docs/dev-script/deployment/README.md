#set( $dollar = '$' )
#set( $hash = '#' )
${hash} ${projectName} 部署工具

本目录按部署流程分层，所有目录与文件名使用英文。Windows 本地使用 PowerShell，Linux 服务器使用 Bash；公共逻辑由 Python 实现。Compose、中间件及 Nginx 配置按 app/environment 分层放在 `docs/dev-ops/`；后端 Dockerfile 位于 `app-backend/${artifactId}-app/Dockerfile`，打包时复制到发布包 `app/Dockerfile`，不在源码中重复维护。

默认后端目录 `/opt/${artifactId}`，前端目录 `/var/www/${artifactId}`，Compose 项目名 `${artifactId}`，HTTP 端口 `${httpPort}`，数据库 `${databaseName}`，数据卷 `${artifactId}_mysql-data`。各项目的容器、数据库和数据卷按 Maven artifactId 隔离。

${hash}${hash} 目录与逐文件说明

```text
deployment/
├── preflight/              ${hash} 部署前检查
├── prepare/                ${hash} 补齐环境、清理旧版本、打包上传
├── deploy/
│   └── iteration/          ${hash} 前端、后端、全量迭代
├── health/                 ${hash} 部署后验收与日常监控
├── uninstall/              ${hash} 服务卸载（后端 `/opt`、前端 `/var/www`）
├── lib/                    ${hash} 公共实现
├── tests/                  ${hash} 工具测试
└── README.md
```

| 文件 | 功能 | 使用方式 / 执行位置 |
| --- | --- | --- |
| `preflight/local-preflight.ps1` | 检查部署源文件（后端 Dockerfile、Nginx、中间件配置/SQL）、本地工具、Node/Python 版本、SSH 公钥与 known_hosts、已有 JAR/dist | Windows：`./preflight/local-preflight.ps1` |
| `preflight/local-preflight.sh` | 同上 | 本地 Linux/macOS：`bash preflight/local-preflight.sh` |
| `preflight/local-preflight.py` | 本地检查实现；不连接服务器，不读取私钥内容 | 由上述入口调用 |
| `preflight/server-preflight.sh` | 检查 Docker/Compose、端口、目录/权限、空间、凭据、残留、待部署产物及 Compose | 服务器：见下方检查流程 |
| `prepare/install-dependencies.sh` | 输出 Ubuntu 安装计划；显式执行时安装 Python、Docker、Compose、SSH 客户端、端口工具等 | 服务器；默认只预览，`--execute` 才安装 |
| `prepare/prepare-server.sh` | 创建目录、管理标记、缺失凭据，修复目录和 `.env` 权限 | 服务器；默认预览，`--fix` 才修改 |
| `prepare/prune-releases.sh` | 删除显式指定的旧发布目录；保护当前、上一版、待恢复版本、运行容器引用的目录 | 服务器；`--release-id ID`，默认预览 |
| `prepare/build-and-upload.ps1` | Windows 打包上传入口，支持全量、单端、仅上传和仅工具上传 | 本地 Windows |
| `prepare/build-and-upload.sh` | 对应 Linux/macOS 打包上传入口 | 本地 Linux/macOS，参数使用 Python CLI 长参数 |
| `prepare/build_upload.py` | 构建检查、发布清单、压缩包、校验、原生 SSH/SCP 上传实现 | 上述两个入口调用 |
| `prepare/.env.example` | 服务器配置格式；占位密码不能用于正式部署 | 参考；真实密码由 prepare 生成 |
| `deploy/first-deploy.sh` | 首次部署；拒绝已有项目容器、数据卷或发布状态 | 在服务器解压后的发布目录执行 |
| `deploy/iteration/frontend.sh` | 前端迭代：仅构建/替换 Nginx，保留后端镜像 | 在服务器新发布目录执行 |
| `deploy/iteration/backend.sh` | 后端迭代：停后端、备份、替换后端、Flyway、重载 Nginx upstream | 在服务器新发布目录执行 |
| `deploy/iteration/full.sh` | 全量迭代；基础设施配置变化或失败恢复使用此入口 | 在服务器新发布目录执行 |
| `deploy/deploy-server.sh` | 底层运维入口：`check/verify/backup/status/logs/stop`，兼容 `init/deploy` 动作 | 服务器，详见运维示例 |
| `health/health-check.sh` | 单次部署验收：容器、API、页面、静态资源、迁移、物理外键 | 在服务器活动发布目录执行 |
| `health/monitor.sh` | 周期巡检，跟随 `current`；异常输出日志，可单次执行 | `--interval 60` 或 `--once`，Ctrl+C 停止 |
| `uninstall/uninstall.sh` | 预览/卸载项目容器与网络；可选数据卷、代码、备份、凭据 | 服务器；默认只预览，见卸载章节 |
| `lib/delivery.py` | 发布文件白名单、哈希、JAR 内迁移、前端资源、路径校验 | Python 公共模块 |
| `lib/bootstrap_server.py` | 校验归档与 SHA-256，安全解压，禁止覆盖已有版本 | 上传目录：`python3 bootstrap_server.py extract ...` |
| `lib/server.py` | 部署、数据库备份、健康检查、锁、单端版本与活动状态管理 | 服务器入口调用 |
| `lib/host.py` | 主机检查、目录准备、旧版本清理、按项目标签卸载的实现 | 服务器入口调用 |
| `tests/test_delivery.py` | 发布包、清单、路径、备份失败保护和 Compose 组合测试 | 本地 unittest |
| `tests/test_lifecycle.py` | 单端版本隔离、清理保护、默认预览与失败中止测试 | 本地 unittest |

`lib` 中的文件需要随工具或发布包一起使用，不应单独移动。源码中的首次部署/迭代入口不直接用于启动应用：它们需要发布包中的 JAR、dist、Compose 和 `release.json`。

${hash}${hash} 前置条件与两类包

本地构建需要 Python 3.12+、Java 21、Maven 3.9+、Node.js **22.22.0**、Corepack、Git；pnpm 版本由 `web/package.json` 固定。上传需要原生 OpenSSH。Windows 不调用 WSL，不使用 SSH ControlMaster，不记录密码。

服务器需要 Linux、Python 3.10+、Docker Engine、Compose 2.24+、`ss`、curl、tar、sha256sum；推荐至少 4 CPU / 8 GiB 内存。检查脚本要求至少 2 GiB 可用磁盘，实际还需预留镜像、数据和备份空间。服务器构建需要访问镜像仓库与 Ubuntu 软件源。

- **工具包** `deployment-tools.tar.gz`：不含应用产物，便于应用上传前先检查服务器。工具放在独立的 `~/${artifactId}-tools` 目录，卸载代码时也可使用。
- **发布包** `<release-id>.tar.gz`：包含完整 JAR、前端、Compose、组件配置，以及 `preflight/prepare/deploy/health/uninstall/lib` 和 README。保留相同脚本分层。包内不含本地构建入口、测试、开发 Compose 或真实 `.env`。

生成物都在项目 `.runtime/delivery/`，附带 `.sha256`。每次成功发布的压缩包需要保留：单端打包要以当前成功包作为基包。发布包解压后不手工修改，校验失败应重新打包。

${hash}${hash} 1. 部署前检查

以下本地命令在 `docs/dev-script/deployment` 执行：

```powershell
./preflight/local-preflight.ps1
${hash} 先上传管理工具，不构建应用
./prepare/build-and-upload.ps1 -ToolsOnly -Server user@your-server
```

服务器登录后，先验证并解压工具包到独立目录。后端发布包、JAR 和 Compose 文件解压在 `/opt/${artifactId}/releases/`；前端构建产物由部署脚本复制到 `/var/www/${artifactId}/releases/`，Nginx 只挂载该目录。若 Python/Docker 尚未安装，可先使用工具里的依赖安装脚本。

```bash
cd ~/${artifactId}-incoming
sha256sum -c deployment-tools.tar.gz.sha256
mkdir -p "${dollar}HOME/${artifactId}-tools"
tar -xzf deployment-tools.tar.gz -C "${dollar}HOME/${artifactId}-tools" --strip-components=1
cd ~/${artifactId}-tools
sudo bash preflight/server-preflight.sh --root /opt/${artifactId} --port ${httpPort} --mode first
```

检查是只读的；没有目录/凭据、Docker 不可达或端口被占用会返回非零。首轮检查的缺项正是准备阶段要处理的内容。检查结果不会显示密码值、私钥或 Docker 容器环境变量。

检查内容：

- Python/Compose 版本、Docker daemon 可访问性、所需命令与磁盘空间。
- 后端 `/opt/${artifactId}` 及前端 `/var/www/${artifactId}` 的读写权限，是否为本工具管理的目录。
- `.env` 中 HTTP 监听、MySQL/Redis/中间件库密码、Nacos token 与身份值、XXL-Job token 和初始管理员密码的格式及权限。
- 项目容器/数据卷/网络、当前和失败发布状态；另只检查当前项目资源，不触碰其他项目。
- HTTP 端口是否被监听或被 Docker 发布。首次要求可用；迭代 `--mode update` 允许当前项目 Nginx 占用该端口。
- 提供 `--release /opt/${artifactId}/releases/ID` 时，检查待部署 JAR、前端资源、迁移哈希、发布清单及 Compose。

模板默认采用 HTTP 同源部署，没有 SSO/JWT/TLS 证书要求。SSH 密钥用于上传认证，可改用密码；HTTPS 如需接入，应由现有入口代理管理证书。本地检查只报告公钥/known_hosts 是否存在，SSH 登录是否成功由实际上传验证。

${hash}${hash} 2. 缺项处理与旧残留处理

${hash}${hash}${hash} 安装环境

```bash
cd ~/${artifactId}-tools
bash prepare/install-dependencies.sh
${hash} 阅读安装计划后手动执行；软件包安装可能启动 Docker daemon
sudo bash prepare/install-dependencies.sh --execute
```

自动安装仅支持 Ubuntu 软件仓库有 `docker-compose-v2` 的版本。已存在 Docker 时拒绝替换，其他发行版或旧 Python 需按系统官方文档补齐，之后重跑检查。不会执行远程安装脚本、自动更新整个系统或改防火墙。

${hash}${hash}${hash} 准备目录和凭据

```bash
sudo bash prepare/prepare-server.sh --root /opt/${artifactId}
sudo bash prepare/prepare-server.sh --root /opt/${artifactId} --fix --port ${httpPort}
```

`--fix` 创建 `releases/`、`backups/` 和管理标记，目录权限分别为 755、700，根目录 700；缺少 `.env` 时生成各组件独立随机凭据和 Nacos Base64 token，权限 600。已有配置只校验和修复权限，不覆盖密码。若数据卷/容器已存在却缺少凭据，停止处理，需恢复原 `.env` 或明确卸载当前项目后重新准备。

端口被其他服务占用时，可选择空闲端口，首次准备用 `--port`；已有配置需手动修改 `.env` 中的 HTTP_PORT，然后检查。不会自动杀掉占用端口的进程。已有数据库的密码不能靠改 `.env` 直接轮换。

${hash}${hash}${hash} 清理多余版本或当前项目

```bash
${hash} 指定版本预览，不默认批量删除
sudo bash prepare/prune-releases.sh --root /opt/${artifactId} --release-id <old-release-id>
${hash} 执行指定版本清理
sudo bash prepare/prune-releases.sh --root /opt/${artifactId} --release-id <old-release-id> \
  --execute --confirm ${artifactId}
```

可重复传 `--release-id`。当前、上一成功版本、待恢复版本、容器引用的版本一律受保护。缺少校验清单或内容损坏的目录不会自动删除。数据残留清理使用文末卸载命令的 `--remove-data`；不会自动删除其他项目或全局执行 Docker prune。

${hash}${hash} 3. 打包上传与解压

在本地 `docs/dev-script/deployment` 执行：

```powershell
${hash} 全量构建、测试与打包，不上传
./prepare/build-and-upload.ps1 -BuildOnly
${hash} 全量构建后上传
./prepare/build-and-upload.ps1 -Server user@your-server
${hash} 重传已验证发布包
./prepare/build-and-upload.ps1 -UploadOnly -Server user@your-server -Package 'D:/path/<release-id>.tar.gz'
```

单端迭代先取**服务器当前成功发布的同一个压缩包及 SHA-256 文件**作为基包：

```powershell
./prepare/build-and-upload.ps1 -Component frontend -BasePackage 'D:/path/<current-id>.tar.gz' -Server user@your-server
./prepare/build-and-upload.ps1 -Component backend -BasePackage 'D:/path/<current-id>.tar.gz' -Server user@your-server
```

前端打包仅重建前端，后端 JAR/迁移从基包复制；后端打包仅重建后端，前端从基包复制。包仍完整，便于后续全量恢复和校验。本地打包时即校验单端边界：前端包不得修改后端 JAR/Dockerfile；后端包不得修改前端资源/Nginx；两者都不得修改 Compose 或其他中间件配置。违规时不会生成新发布包，也不会上传；服务器部署时再次执行相同校验。

Linux/macOS 参数对应：

```bash
bash prepare/build-and-upload.sh --build-only
bash prepare/build-and-upload.sh --component frontend --base-package /path/current.tar.gz --server user@your-server
```

可设置 `-SshPort 2222 / --ssh-port 2222`、`-RemoteDir incoming / --remote-dir incoming`。默认上传至用户家目录 `${artifactId}-incoming`，密码认证会在 mkdir 和 scp 两次连接时各询问一次；推荐使用配置好的密钥与 ssh-agent。

全量构建执行 Maven 打包和不监听端口的 单元测试，以及前端类型检查、ESLint、Vitest、Vite build；不运行开发服务或真实数据库集成测试。

服务器解压：

```bash
cd ~/${artifactId}-incoming
sha256sum -c <release-id>.tar.gz.sha256
sudo python3 ./bootstrap_server.py extract --root /opt/${artifactId} \
  --package "${dollar}HOME/${artifactId}-incoming/<release-id>.tar.gz"
cd /opt/${artifactId}/releases/<release-id>
sudo bash preflight/server-preflight.sh --root /opt/${artifactId} --mode first --release "${dollar}PWD"
```

bootstrap 和 delivery 两个引导文件会同时上传到 incoming；引导程序验证归档路径、哈希、清单、应用产物后解压，拒绝覆盖已有版本。后续迭代检查改用 `--mode update`。

${hash}${hash} 4. 正式部署

${hash}${hash}${hash} 首次部署

```bash
cd /opt/${artifactId}/releases/<release-id>
sudo bash deploy/first-deploy.sh --root /opt/${artifactId}
```

先完成 prepare；首次脚本不会悄悄覆盖旧库或旧凭据。遇到已有 项目容器、数据卷或发布记录，会拒绝首次模式。部署动作内部还会执行一次 preflight，检查通过才构建/启动。

流程：校验 → 将后端发布目录保留在 `/opt`、将前端静态文件复制到 `/var/www` → 构建镜像 → MySQL、Redis、Nacos、RocketMQ、XXL-Job 就绪 → 应用启动/Flyway → Nginx → 健康验收 → 更新 `current`。初始 V1 仅登记基线，不创建业务表。在项目中新增 Flyway 迁移；不手工重复执行 SQL。

${hash}${hash}${hash} 日常迭代

每次在**新解压发布目录**执行一种入口：

```bash
sudo bash deploy/iteration/frontend.sh --root /opt/${artifactId}
sudo bash deploy/iteration/backend.sh --root /opt/${artifactId}
sudo bash deploy/iteration/full.sh --root /opt/${artifactId}
```

| 模式 | 改动与保护 |
| --- | --- |
| 前端 | 校验后端/数据库/Compose 与当前包一致；仅重建 Nginx，保留后端实际镜像版本 |
| 后端 | 校验前端/Nginx/数据库/Compose 一致；停后端、备份非空库、替换后端/Flyway；重载 Nginx 以解析新后端地址 |
| 全量 | 构建两端、确认 MySQL 就绪、停两端、备份非空库、替换两端；用于配置变更和失败恢复 |

单端模式必须已有成功部署和完整 `active.json`，并且容器镜像/健康状态与记录一致。`current` 始终指向最后成功的完整发布包；`active.json` 分别记录后端和前端实际镜像标签。部署失败保留 pending 状态，健康检查会报错，不会假装旧 `current` 仍是运行版本。失败后到失败目录看日志，修复后用全量迭代恢复。

后端/全量备份失败会中止启动新应用，停下来的服务不自动恢复；存在短暂停机。MySQL DDL 不自动回滚，禁止自动 Flyway clean/baseline/repair。所有更新都保持原数据卷名。

${hash}${hash} 5. 部署后健康检查和日常监控

```bash
cd /opt/${artifactId}/current
sudo bash health/health-check.sh --root /opt/${artifactId}
sudo bash health/monitor.sh --root /opt/${artifactId} --once
sudo bash health/monitor.sh --root /opt/${artifactId} --interval 60
```

检查容器健康和镜像标签、readiness、API 连通性、页面/SPA 路由、JS/CSS 内容、Flyway 迁移集合、失败迁移以及物理外键数量为零。周期监控每轮重新跟随 `current`，异常输出近期日志，单次模式异常返回非零。监控不自动重启或修库；需要后台常驻时由维护人员自行配置 systemd，不默认安装定时任务。

其他日常命令：

```bash
sudo bash deploy/deploy-server.sh status --root /opt/${artifactId}
sudo bash deploy/deploy-server.sh logs --root /opt/${artifactId}
sudo bash deploy/deploy-server.sh backup --root /opt/${artifactId}
sudo bash deploy/deploy-server.sh stop --root /opt/${artifactId}
```

备份保存 `backups/*.sql.gz`，权限 600。更新前在应用停止后备份；手动 backup 使用单事务快照。备份、`.env` 与发布包应另存到独立存储。恢复需停应用并由维护人员恢复到独立空库，选择兼容包再部署，本工具不自动恢复数据。

${hash}${hash} 6. 服务卸载（后端 `/opt`、前端 `/var/www`）

建议从独立工具目录执行，避免删除脚本自身所在的发布目录：

```bash
cd ~/${artifactId}-tools
${hash} 默认只展示当前项目容器和网络的删除清单
sudo bash uninstall/uninstall.sh --root /opt/${artifactId}
${hash} 只卸载容器/网络，保留卷、代码、凭据和备份
sudo bash uninstall/uninstall.sh --root /opt/${artifactId} --execute --confirm ${artifactId}
${hash} 预览包括数据卷和服务代码的清理
sudo bash uninstall/uninstall.sh --root /opt/${artifactId} --remove-data --remove-code
${hash} 明确执行（数据库数据不可恢复，务必先保留需要的备份）
sudo bash uninstall/uninstall.sh --root /opt/${artifactId} --remove-data --remove-code \
  --execute --confirm ${artifactId}
```

| 参数 | 删除范围 |
| --- | --- |
| 默认 | 仅预览；计划中含当前项目容器及网络 |
| `--remove-data` | 加上本 Compose 项目标签的数据卷 |
| `--remove-code` | 加上 `/opt/${artifactId}` 的 releases、current、上一版本记录及 active 状态，以及 `/var/www/${artifactId}` 的前端 releases/current |
| `--remove-backups` | 单独选择删除数据库备份；删代码不隐含删备份 |
| `--remove-config` | 删除服务器 `.env`，必须同时选择 `--remove-data` |
| `--execute --confirm ${artifactId}` | 执行所选清单，缺少时只预览 |

卸载按 Docker Compose **项目标签**识别，不按宽泛名称匹配，不调用全局 prune。网络/卷被其他项目使用时拒绝清理，Docker 操作失败即停止，不吞掉异常后宣称成功。仅操作带本工具管理标记的规范绝对目录，拒绝共享系统目录、符号链接跳转和其他项目目录。镜像、incoming 上传包、独立工具目录默认保留。

${hash}${hash} 本地验证与边界

在 项目根目录：

```powershell
python -m unittest discover -s docs/dev-script/deployment/tests -p 'test_*.py'
```

单元测试使用临时目录与模拟 Docker，不会启动服务或删除真实资源。另检查 PowerShell/Bash 语法、Compose 静态展开和打包路径。真实镜像构建、服务器网络、数据库迁移和浏览器验收需在获准实际部署后验证。

${hash}${hash} 中间件与目录变更

发布包使用 environment/docker-compose.yml 和 app/docker-compose.yml，组件配置和 SQL 随包交付。首次/全量迭代启动全部中间件；单端迭代拒绝中间件文件变更。验收检查全部组件健康，卸载按项目标签覆盖所有组件/命名卷。开发覆盖文件和本地 .env 不进入发布包。

自动 backup 仅备份业务库，中间件库/数据卷需单独备份。已有部署先保留原凭据并补齐新增变量、备份和初始化中间件库，再运行全量迭代。详情见源码 docs/dev-ops/environment/sql/README.md。Nacos 首次需通过受控入口设置管理员密码，XXL-Job 初始密码在服务器 .env 的 XXL_JOB_ADMIN_PASSWORD 中。

${hash}${hash} 源码到发布包的映射

所有源路径统一以生成项目根目录解析，本地预检查及构建前按白名单检查文件。真实 `.env` 不纳入发布包。

| 源码路径 | 发布包路径 |
| --- | --- |
| app-backend/${artifactId}-app/Dockerfile | app/Dockerfile |
| docs/dev-ops/app/docker-compose.yml | app/docker-compose.yml |
| docs/dev-ops/environment/nginx/ 下的 Dockerfile、conf.d/default.conf | environment/nginx/ 对应文件 |
| docs/dev-ops/environment/ 中生产 Compose、组件配置和 SQL 白名单 | environment/ 对应文件 |
| docs/dev-script/deployment/ 中的服务器脚本白名单 | preflight/prepare/deploy/health/uninstall/lib 对应文件 |

Dockerfile 源码默认读取模块 target 中的 JAR；发布包 Compose 通过 `JAR_FILE=app.jar` 读取包内 JAR。前端或后端单独迭代继续使用原有 PS1/SH 参数，不需要更改调用命令。
