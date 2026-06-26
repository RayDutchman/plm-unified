# Kafka 消息格式说明

> 来源：从 DocDoku PLM 源码分析（`ConverterBean.java`、`ConversionOrder.java`、`ConversionOrderDeserializer.java`）

---

## Topic

```
CONVERT
```

## 生产者（DocDoku back 容器 → 现改为新 FastAPI 后端）

- Bootstrap servers: `kafka:9092`
- Key serializer: `StringSerializer`（Key 为 `partIterationKey.toString()`，即 `{workspaceId}/{number}/{version}-{iteration}`）
- Value serializer: 自定义 `ConversionOrderSerializer`（JSON 序列化，使用 Jakarta JSON-B）
- acks: `0`（fire-and-forget）
- retries: `1`
- linger.ms: `33`

## 消费者（conversion 容器，不改动）

- Group ID: 见 conversion 服务配置
- Value deserializer: `ConversionOrderDeserializer`（JSON 反序列化为 `ConversionOrder` 对象）

---

## 消息结构

消息 Value 为 JSON，对应 Java 类 `ConversionOrder`，序列化后格式如下：

```json
{
  "partIterationKey": {
    "partRevision": {
      "partMaster": {
        "workspace": "Workspace_0",
        "number": "PART-001"
      },
      "version": "A"
    },
    "iteration": 1
  },
  "binaryResource": {
    "fullName": "Workspace_0/parts/PART-001/A/1/nativecad/model.stp",
    "contentLength": 204800,
    "lastModified": "2026-06-26T09:00:00Z"
  },
  "userToken": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9..."
}
```

### 字段说明

| 字段路径 | 类型 | 说明 |
|---|---|---|
| `partIterationKey.partRevision.partMaster.workspace` | string | 工作空间 ID，如 `Workspace_0` |
| `partIterationKey.partRevision.partMaster.number` | string | 零件编号，如 `PART-001` |
| `partIterationKey.partRevision.version` | string | 版本号，单字母，如 `A` |
| `partIterationKey.iteration` | int | 迭代号，从 1 开始 |
| `binaryResource.fullName` | string | vault 中的完整文件路径（主键），格式：`{workspace}/parts/{number}/{version}/{iteration}/nativecad/{filename}` |
| `binaryResource.contentLength` | long | 文件字节大小 |
| `binaryResource.lastModified` | timestamp | 文件最后修改时间（ISO 8601） |
| `userToken` | string | 发起上传的用户 JWT Token，conversion 回调时用于鉴权 |

### 消息 Key

```
{workspaceId}/{partNumber}/{version}-{iteration}
```

示例：`Workspace_0/PART-001/A-1`

---

## Python 端实现要点（新 FastAPI 后端）

```python
import json
from aiokafka import AIOKafkaProducer

KAFKA_TOPIC = "CONVERT"

async def send_conversion_order(
    workspace_id: str,
    part_number: str,
    version: str,
    iteration: int,
    file_full_name: str,
    file_size: int,
    user_token: str
):
    """
    向 Kafka topic CONVERT 发送转换任务。
    消息格式必须与 DocDoku ConversionOrder 的 JSON-B 序列化完全一致，
    否则 conversion 容器（Java）无法反序列化。
    """
    message = {
        "partIterationKey": {
            "partRevision": {
                "partMaster": {
                    "workspace": workspace_id,
                    "number": part_number
                },
                "version": version
            },
            "iteration": iteration
        },
        "binaryResource": {
            "fullName": file_full_name,
            "contentLength": file_size,
            "lastModified": datetime.utcnow().isoformat() + "Z"
        },
        "userToken": user_token
    }
    key = f"{workspace_id}/{part_number}/{version}-{iteration}"

    producer = AIOKafkaProducer(bootstrap_servers="kafka:9092")
    await producer.start()
    try:
        await producer.send(
            KAFKA_TOPIC,
            key=key.encode(),
            value=json.dumps(message).encode()
        )
    finally:
        await producer.stop()
```

---

## 注意事项

1. **JSON-B 序列化规则**：Java JSON-B 默认使用字段名作为 JSON key，无自定义 `@JsonbProperty`，字段名必须完全匹配（区分大小写）
2. **userToken**：conversion 服务完成后会调用 back 的回调接口，携带此 token 鉴权；新 FastAPI 后端的回调接口必须接受并验证此 token
3. **acks=0**：原始配置为 fire-and-forget，Python 端保持一致，不等待 broker 确认
4. **fullName 路径格式**：必须严格遵守 `{workspace}/parts/{number}/{version}/{iteration}/nativecad/{filename}`，conversion 服务按此路径读取文件
