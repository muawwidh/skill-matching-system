from statistics import mean


def retrieval_metrics(judgments: list[dict]) -> dict:
    if not judgments:
        raise ValueError("A human-labelled evaluation set is required.")
    scores = {5: [], 10: [], 20: []}
    reciprocal = []
    for item in judgments:
        relevant = set(item["relevant_job_ids"])
        ranked = item["retrieved_job_ids"]
        if not relevant:
            raise ValueError("Every evaluation query needs at least one relevant job.")
        for k in scores:
            scores[k].append(len(relevant.intersection(ranked[:k])) / len(relevant))
        reciprocal.append(next((1 / rank for rank, job in enumerate(ranked, 1) if job in relevant), 0.0))
    return {**{f"recall_at_{k}": mean(values) for k, values in scores.items()},
            "mrr": mean(reciprocal), "queries": len(judgments)}
