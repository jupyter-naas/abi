# Bus Service

`BusService` provides topic/routing-key pub-sub used internally and by modules.

Related pages: [[services/Triple-Store]], [[services/Overview]].

## Core API

- `topic_publish(topic, routing_key, payload)`
- `topic_consume(topic, routing_key, callback) -> Thread`

## Adapter options

- `python_queue`: in-process queue bus (great for local/dev).
- `rabbitmq`: durable topic exchange + durable queues.
- `custom`: pluggable adapter.

## Routing pattern support

Adapters use topic-style routing patterns:

- `*` for one token
- `#` for many tokens

This is used by triple-store event subscriptions.

## Example

```yaml
services:
  bus:
    bus_adapter:
      adapter: "python_queue"
      config: {}
```
