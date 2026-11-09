#set( $dollar = '$' )
#set( $hash = '#' )
/*
 * description: 应用启动入口，装配 Spring Boot 与各业务模块。
 * author: zzy
 * created: 2026-10-19
 */
package ${groupId.replace('-', '_')}.${artifactId.replace('-', '_')};

import org.springframework.boot.SpringApplication;
import org.springframework.boot.autoconfigure.SpringBootApplication;

/** 从根包装配各模块；启动时按配置连接数据库并执行 Flyway 迁移。 */
@SpringBootApplication
public class Application {
    /**
     * 启动 Spring 应用和内嵌 HTTP 服务。
     * @param args Spring Boot 命令行参数，可覆盖环境和应用配置
     */
    public static void main(String[] args) {
        SpringApplication.run(Application.class, args);
    }
}
