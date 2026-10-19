#set( $dollar = '$' )
#set( $hash = '#' )
/**
 * 消息监听入口；按需引入消息 SDK，处理幂等并调用领域服务。
 */
package com.rain.${artifactId.replace('-', '_')}.trigger.listener;
