"""检索评估指标：MRR（首位倒数秩）和 Recall@k（召回率）。"""


def mrr(predicted: list[str], relevant: list[str]) -> float:
    """计算 Mean Reciprocal Rank。

    predicted  = 检索返回的片段标识符列表，按分数降序排列
    relevant   = 人工标注的相关片段标识符列表
    返回值     = 第一个相关结果排名的倒数，如果没有命中则返回 0

    例如：相关片段在排第 3 位 → 1/3 = 0.333
    """
    for i, item in enumerate(predicted, start=1):
        if item in relevant:
            return 1.0 / i
    return 0.0


def recall_at_k(predicted: list[str], relevant: list[str], k: int) -> float:
    """计算 top-k 召回率。

    在 top-k 个检索结果中，有多少比例的相关片段被成功召回。
    返回值在 0.0 ~ 1.0 之间。

    例如：标注了 4 个相关片段，top-5 里命中了 3 个 → 3/4 = 0.75
    """
    if not relevant:
        return 0.0
    predicted_k = predicted[:k]
    hits = sum(1 for r in relevant if r in predicted_k)
    return hits / len(relevant)


def evaluate_one(
    predicted_ids: list[str],
    relevant_ids: list[str],
    k_values: list[int] | None = None,
) -> dict:
    """对单个测试用例计算所有指标，返回一个汇总 dict。"""
    if k_values is None:
        k_values = [5, 10, 20]

    result = {"mrr": round(mrr(predicted_ids, relevant_ids), 4)}

    for k in k_values:
        result[f"recall@{k}"] = round(recall_at_k(predicted_ids, relevant_ids, k), 4)

    return result
