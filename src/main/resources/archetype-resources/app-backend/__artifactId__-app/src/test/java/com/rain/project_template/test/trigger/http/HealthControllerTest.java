#set( $dollar = '$' )
#set( $hash = '#' )
/*
 * description: 在内存中验证健康接口与异常响应契约。
 * author: zzy
 * created: 2026-10-19
 */
package ${groupId.replace('-', '_')}.${artifactId.replace('-', '_')}.test.trigger.http;

import ${groupId.replace('-', '_')}.${artifactId.replace('-', '_')}.trigger.http.ApiExceptionHandler;
import ${groupId.replace('-', '_')}.${artifactId.replace('-', '_')}.trigger.http.HealthController;
import ${groupId.replace('-', '_')}.${artifactId.replace('-', '_')}.types.common.Constants.ResponseCode;
import ${groupId.replace('-', '_')}.${artifactId.replace('-', '_')}.types.exception.BusinessException;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.springframework.test.web.servlet.MockMvc;
import org.springframework.test.web.servlet.setup.MockMvcBuilders;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.RestController;

import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.get;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.jsonPath;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.status;

/** Verifies HTTP contracts in memory, without starting a server or connecting to a database. */
class HealthControllerTest {
    private MockMvc mvc;

    @BeforeEach
    void setUp() {
        mvc = MockMvcBuilders.standaloneSetup(new HealthController(), new FailureController())
                .setControllerAdvice(new ApiExceptionHandler())
                .build();
    }

    @Test
    void pingReturnsSuccessfulApiEnvelope() throws Exception {
        mvc.perform(get("/api/v1/ping"))
                .andExpect(status().isOk())
                .andExpect(jsonPath("${dollar}.code").value("00000"))
                .andExpect(jsonPath("${dollar}.message").value("成功"));
    }

    @Test
    void businessFailureUsesThePublicErrorContract() throws Exception {
        mvc.perform(get("/test/business-failure"))
                .andExpect(status().isBadRequest())
                .andExpect(jsonPath("${dollar}.code").value("A0400"))
                .andExpect(jsonPath("${dollar}.message").value("用户请求参数错误"));
    }

    @Test
    void unexpectedFailureDoesNotExposeInternalDetails() throws Exception {
        mvc.perform(get("/test/unexpected-failure"))
                .andExpect(status().isInternalServerError())
                .andExpect(jsonPath("${dollar}.code").value("B0001"))
                .andExpect(jsonPath("${dollar}.message").value("系统执行出错"));
    }

    @Test
    void systemBusinessFailureReturnsServerError() throws Exception {
        mvc.perform(get("/test/system-failure"))
                .andExpect(status().isInternalServerError())
                .andExpect(jsonPath("${dollar}.code").value("B0001"));
    }

    @Test
    void dependencyFailureDoesNotExposeItsCause() throws Exception {
        mvc.perform(get("/test/dependency-failure"))
                .andExpect(status().isServiceUnavailable())
                .andExpect(jsonPath("${dollar}.code").value("C0001"))
                .andExpect(jsonPath("${dollar}.message").value("调用第三方服务出错"));
    }

    @Test
    void businessExceptionPreservesMessageAndCause() {
        var cause = new IllegalStateException("Internal connection details");
        var exception = new BusinessException(ResponseCode.THIRD_PARTY_ERROR, cause);
        org.junit.jupiter.api.Assertions.assertEquals("调用第三方服务出错", exception.getMessage());
        org.junit.jupiter.api.Assertions.assertSame(cause, exception.getCause());
    }

    @RestController
    static class FailureController {
        @GetMapping("/test/business-failure")
        public void businessFailure() {
            throw new BusinessException(ResponseCode.ILLEGAL_PARAMETER);
        }

        @GetMapping("/test/system-failure")
        public void systemFailure() {
            throw new BusinessException(ResponseCode.SYSTEM_ERROR);
        }

        @GetMapping("/test/dependency-failure")
        public void dependencyFailure() {
            throw new BusinessException(ResponseCode.THIRD_PARTY_ERROR,
                    new IllegalStateException("Internal connection details"));
        }

        @GetMapping("/test/unexpected-failure")
        public void unexpectedFailure() {
            throw new IllegalStateException("Internal storage details");
        }
    }
}
