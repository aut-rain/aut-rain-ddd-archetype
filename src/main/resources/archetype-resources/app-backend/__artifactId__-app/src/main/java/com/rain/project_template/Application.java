#set( $dollar = '$' )
#set( $hash = '#' )
package com.rain.${artifactId.replace('-', '_')};

import org.springframework.boot.SpringApplication;
import org.springframework.boot.autoconfigure.SpringBootApplication;

@SpringBootApplication
public class Application {
    public static void main(String[] args) {
        SpringApplication.run(Application.class, args);
    }
}
