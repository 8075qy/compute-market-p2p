class RedisKeys:
    # 节点心跳状态：ZSET，成员 node_id，分数 last_heartbeat_ts
    NODE_HEARTBEAT_ZSET = "node:heartbeat"
    # 节点在线标记：STRING node_id -> "1" (TTL 6min，心跳续期)
    NODE_ONLINE_FLAG = "node:online:{node_id}"
    # 任务调度队列：LIST，按优先级/创建时间排序
    TASK_SCHEDULING_QUEUE = "task:scheduling:queue"
    # 任务分配锁：SETNX task_id -> node_id (TTL 5min)
    TASK_ASSIGN_LOCK = "task:assign:lock:{task_id}"
    # 分布式锁通用
    DIST_LOCK = "lock:{resource}"
    # 速率限制：滑动窗口
    RATE_LIMIT = "ratelimit:{user_id}:{endpoint}"
    # 会话：STRING session_id -> user_json (TTL 7d)
    SESSION = "session:{session_id}"
    # 验证码：STRING phone/email -> code (TTL 5min)
    VERIFICATION_CODE = "verify:{contact}"
    # 实时在线节点数缓存
    ONLINE_NODE_COUNT = "stats:online_nodes"
    # 待调度任务数缓存
    PENDING_TASK_COUNT = "stats:pending_tasks"
    # 任务进度推送频道
    TASK_PROGRESS_CHANNEL = "task:progress:{task_id}"
    # 批处理任务分配游标：STRING task_id -> 已分配工作项数（INCRBY 原子递增）
    BATCH_CURSOR = "batch:cursor:{task_id}"
