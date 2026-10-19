#set( $dollar = '$' )
#set( $hash = '#' )
package com.rain.${artifactId.replace('-', '_')}.types.validation;

import com.rain.${artifactId.replace('-', '_')}.types.exception.BusinessException;

/** Small, dependency-free guard methods for domain and application services. */
public final class ValidationUtils {
    private ValidationUtils() {
    }

    public static <T> T requireNonNull(T value, String field) {
        if (value == null) {
            throw new BusinessException("VALIDATION_ERROR", field + " must not be null");
        }
        return value;
    }

    public static String requireText(String value, String field) {
        if (value == null || value.isBlank()) {
            throw new BusinessException("VALIDATION_ERROR", field + " must not be blank");
        }
        return value;
    }
}
