#set( $dollar = '$' )
#set( $hash = '#' )
package com.rain.${artifactId.replace('-', '_')}.trigger.http;

import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.RestController;

import com.rain.${artifactId.replace('-', '_')}.types.model.ApiResponse;

@RestController
public class HealthController {
    @GetMapping("/api/v1/ping")
    public ApiResponse<Void> ping() {
        return ApiResponse.success(null);
    }
}
