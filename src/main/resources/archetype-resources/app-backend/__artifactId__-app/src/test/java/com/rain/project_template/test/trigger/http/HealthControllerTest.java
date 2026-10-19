#set( $dollar = '$' )
#set( $hash = '#' )
package com.rain.${artifactId.replace('-', '_')}.test.trigger.http;

import com.rain.${artifactId.replace('-', '_')}.trigger.http.ApiExceptionHandler;
import com.rain.${artifactId.replace('-', '_')}.trigger.http.HealthController;
import com.rain.${artifactId.replace('-', '_')}.types.exception.BusinessException;
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
                .andExpect(jsonPath("${dollar}.code").value("0"))
                .andExpect(jsonPath("${dollar}.message").value("success"));
    }

    @Test
    void businessFailureUsesThePublicErrorContract() throws Exception {
        mvc.perform(get("/test/business-failure"))
                .andExpect(status().isBadRequest())
                .andExpect(jsonPath("${dollar}.code").value("INVALID_INPUT"))
                .andExpect(jsonPath("${dollar}.message").value("Invalid input"));
    }

    @Test
    void unexpectedFailureDoesNotExposeInternalDetails() throws Exception {
        mvc.perform(get("/test/unexpected-failure"))
                .andExpect(status().isInternalServerError())
                .andExpect(jsonPath("${dollar}.code").value("INTERNAL_ERROR"))
                .andExpect(jsonPath("${dollar}.message").value("Internal server error"));
    }

    @RestController
    static class FailureController {
        @GetMapping("/test/business-failure")
        public void businessFailure() {
            throw new BusinessException("INVALID_INPUT", "Invalid input");
        }

        @GetMapping("/test/unexpected-failure")
        public void unexpectedFailure() {
            throw new IllegalStateException("Internal storage details");
        }
    }
}
