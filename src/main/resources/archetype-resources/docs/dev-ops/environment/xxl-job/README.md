#set( $dollar = '$' )
#set( $hash = '#' )
${hash} XXL-Job
镜像 xuxueli/xxl-job-admin:2.4.1，数据库/用户 xxl_job，内部监听 9090，开发地址 http://127.0.0.1:9090/xxl-job-admin。

初始管理员 admin，密码为 XXL_JOB_ADMIN_PASSWORD，初始化脚本按上游格式写入 MD5；没有保留 123456 默认密码或示例任务。已有卷修改环境变量不会重置账号，应通过应用修改密码。

XXL_JOB_ACCESS_TOKEN 用于调度中心与执行器通信，与管理员密码不同。业务接入时配置相同 token、可回调执行器地址及端口；仅启动管理中心不代表已集成任务执行。

生产不发布管理端口，使用受控网络或 SSH 隧道访问。健康检查只确认端口监听，上线应登录并执行测试任务验证。
