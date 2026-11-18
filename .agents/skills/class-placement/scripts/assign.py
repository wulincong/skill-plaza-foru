#!/usr/bin/env python3
"""智能分班确定性求解器（纯标准库）。

用法（在会话工作区运行，脚本用技能安装目录的绝对路径）：
    python3 <技能目录>/scripts/assign.py params.json students.json --out output/placement-<stamp>

输出目录：result.json、audit/（manifest.json + solver-log.jsonl 哈希链）、roster/（每班 CSV + 全员 CSV）。
同一输入与同一种子得到相同的分班结果；一次受控重掷由状态文件限制为至多两次求解（attempt 1/2）。
"""

import argparse
import csv
import hashlib
import json
import math
import random
import sys
import time
from pathlib import Path

SOLVER_VERSION = "1.1.0"
KNOWN_FIELDS = ["id", "name", "gender", "region", "score", "assessment", "preference"]
GENDER_KEYS = {"男": "男", "女": "女", "m": "男", "f": "女", "male": "男", "female": "女"}


def canonical(obj) -> str:
    return json.dumps(obj, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def sha256_file(path: Path) -> str:
    return sha256_text(path.read_text(encoding="utf-8"))


def fail(message: str):
    print(f"assign.py: {message}", file=sys.stderr)
    raise SystemExit(2)


def mean(values):
    return sum(values) / len(values) if values else 0.0


def pstdev(values):
    if len(values) < 2:
        return 0.0
    m = mean(values)
    return math.sqrt(sum((v - m) ** 2 for v in values) / len(values))


def to_float(v):
    if v is None or isinstance(v, bool):
        return None
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


def normalize_gender(value):
    if value is None:
        return None
    return GENDER_KEYS.get(str(value).strip().lower())


def numeric_column(students, field):
    vals, missing = [], 0
    for s in students:
        v = to_float(s.get(field))
        if v is None:
            missing += 1
        else:
            vals.append(v)
    return vals, missing


def categorical_column(students, field):
    vals, missing = [], 0
    for s in students:
        v = normalize_gender(s.get(field)) if field == "gender" else s.get(field)
        if v is None or str(v).strip() == "":
            missing += 1
        else:
            vals.append(str(v).strip())
    return vals, missing


# ---------------------------------------------------------------- 求解日志（哈希链）

class SolverLog:
    """逐事件追加写入，每条携带前一条哈希，末链头写入 manifest，事后篡改可被发现。"""

    def __init__(self, path: Path):
        self.path = path
        self.seq = 0
        self.prev = sha256_text("genesis")
        self.t0 = time.time()

    def event(self, event_kind, **payload):
        row = {"seq": self.seq, "at": round(time.time() - self.t0, 3), "kind": event_kind, **payload}
        line = canonical(row)
        head = sha256_text(self.prev + line)
        with self.path.open("a", encoding="utf-8") as fh:
            fh.write(canonical({**row, "prev": self.prev, "hash": head}) + "\n")
        self.seq += 1
        self.prev = head

    @property
    def head(self):
        return self.prev


# ---------------------------------------------------------------- 约束

def build_units(students, constraints):
    """same-class 约束合并为不可拆分单元；返回 (units: list[tuple[int]], id 索引)。"""
    index = {str(s["id"]): i for i, s in enumerate(students)}
    parent = list(range(len(students)))

    def find(x):
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    for c in constraints:
        if c.get("type") == "same-class":
            ids = [str(x) for x in c.get("students", [])]
            for x in ids:
                if x not in index:
                    fail(f"约束引用了不存在的学生：{x}")
            for x in ids[1:]:
                ra, rb = find(index[ids[0]]), find(index[x])
                if ra != rb:
                    parent[max(ra, rb)] = min(ra, rb)

    groups = {}
    for i in range(len(students)):
        groups.setdefault(find(i), []).append(i)
    units = [tuple(sorted(group, key=lambda i: str(students[i]["id"]))) for _r, group in sorted(groups.items())]
    return units, index


def separation_pairs(constraints, index):
    pairs = []
    for c in constraints:
        if c.get("type") == "different-class":
            ids = [str(x) for x in c.get("students", [])]
            if len(ids) != 2:
                fail("different-class 约束必须且只能包含两名学生")
            for x in ids:
                if x not in index:
                    fail(f"约束引用了不存在的学生：{x}")
            pairs.append(tuple(ids))
    return pairs


# ---------------------------------------------------------------- 均衡模式

class BalancedSolver:
    """均衡分班：综合分蛇形铺班 + 受种子驱动的局部搜索（增量目标：各班维度均值/构成对全局的偏差平方和）。"""

    def __init__(self, students, params, seed, log):
        self.students = students
        self.params = params
        self.rng = random.Random(seed)
        self.log = log
        self.k = int(params["classCount"])
        self.cap = int(params["capacityPerClass"])
        self.units, self.index = build_units(students, params.get("constraints", []))
        self.pairs = separation_pairs(params.get("constraints", []), self.index)
        self.dims = self._load_dims()
        self.unit_score = self._unit_composite()
        self.unit_agg = self._unit_aggregates()

    def _unit_aggregates(self):
        """每单元的维度聚合（数值和/计数、分类计数），局部搜索增量评估直接复用。"""
        out = {}
        for unit in self.units:
            agg = {"num": {}, "cat": {}}
            for d in self.dims:
                if d["kind"] == "numeric":
                    s = n = 0
                    for i in unit:
                        v = to_float(self.students[i].get(d["field"]))
                        if v is not None:
                            s += v
                            n += 1
                    agg["num"][d["field"]] = (s, n)
                else:
                    counts = {v: 0 for v in d["values"]}
                    for i in unit:
                        v = normalize_gender(self.students[i].get(d["field"])) if d["field"] == "gender" else self.students[i].get(d["field"])
                        if v is not None and str(v).strip() != "":
                            counts[str(v).strip()] += 1
                    agg["cat"][d["field"]] = counts
            out[unit] = agg
        return out

    def _load_dims(self):
        dims = []
        raw_dims = self.params.get("dimensions") or [{"field": "score", "weight": 0.7}, {"field": "gender", "weight": 0.3}]
        for d in raw_dims:
            field = str(d.get("field") or "").strip()
            if not field:
                fail("均衡维度缺少 field")
            vals, missing = numeric_column(self.students, field)
            if len(vals) >= max(2, len(self.students) // 2):
                dims.append({"field": field, "kind": "numeric", "weight": float(d.get("weight", 1)),
                             "mean": mean(vals), "std": pstdev(vals) or 1.0, "missing": missing})
                continue
            cats, missing = categorical_column(self.students, field)
            if cats:
                counts = {}
                for v in cats:
                    counts[v] = counts.get(v, 0) + 1
                dims.append({"field": field, "kind": "categorical", "weight": float(d.get("weight", 1)),
                             "values": sorted(counts), "share": {v: c / len(cats) for v, c in counts.items()},
                             "missing": missing})
                continue
            fail(f"均衡维度 {field} 在名单中没有足够取值（数值需过半可用，分类需至少 1 个）")
        total = sum(d["weight"] for d in dims) or 1.0
        for d in dims:
            d["weight"] = d["weight"] / total
        return dims

    def _unit_composite(self):
        scores = {}
        for unit in self.units:
            total = 0.0
            for d in self.dims:
                if d["kind"] != "numeric":
                    continue
                vals = [to_float(self.students[i].get(d["field"])) for i in unit]
                vals = [v if v is not None else d["mean"] for v in vals]
                total += d["weight"] * (mean(vals) - d["mean"]) / d["std"]
            scores[unit] = total
        return scores

    # -- 班级聚合与目标 ---------------------------------------------------

    def _new_agg(self):
        return {"count": 0,
                "num": {d["field"]: {"sum": 0.0, "n": 0} for d in self.dims if d["kind"] == "numeric"},
                "cat": {d["field"]: {v: 0 for v in d["values"]} for d in self.dims if d["kind"] == "categorical"}}

    def _apply(self, agg, unit, sign):
        agg["count"] += sign * len(unit)
        cached = self.unit_agg[unit]
        for field, (s, n) in cached["num"].items():
            slot = agg["num"][field]
            slot["sum"] += sign * s
            slot["n"] += sign * n
        for field, counts in cached["cat"].items():
            slot = agg["cat"][field]
            for v, c in counts.items():
                slot[v] += sign * c

    def _agg_cost(self, agg):
        """可分离目标：Σ 维度权重 ×（该班均值/构成相对全局的偏差平方）。"""
        if agg["count"] == 0:
            return 0.0
        cost = 0.0
        for d in self.dims:
            w = d["weight"]
            if d["kind"] == "numeric":
                slot = agg["num"][d["field"]]
                if slot["n"]:
                    m = slot["sum"] / slot["n"]
                    cost += w * ((m - d["mean"]) / d["std"]) ** 2
            else:
                slot = agg["cat"][d["field"]]
                total = sum(slot.values())
                if total:
                    for v in d["values"]:
                        cost += w * (slot[v] / total - d["share"][v]) ** 2
        return cost

    def _objective(self, aggs):
        return sum(self._agg_cost(a) for a in aggs)

    # -- 初始解：蛇形 -----------------------------------------------------

    def solve(self):
        self.pairs_of = {}
        for a, b in self.pairs:
            self.pairs_of.setdefault(a, set()).add(b)
            self.pairs_of.setdefault(b, set()).add(a)
        # 综合分 + 受种子抖动后蛇形铺班：抖动只打乱相邻名次，保留高→低的整体结构，
        # 使均值天然均衡且班内高/中/低混合；不同种子得到可区分的初始解与最终解。
        jitter = {u: self.rng.gauss(0, 0.35) for u in range(len(self.units))}
        order = sorted(range(len(self.units)), key=lambda u: (-(self.unit_score[self.units[u]] + jitter[u]), u))
        assign = {}
        counts = [0] * self.k
        forward = True
        cursor = 0
        for u in order:
            unit = self.units[u]
            placed = False
            for hop in range(self.k):
                c = (cursor + hop) % self.k if forward else (cursor - hop) % self.k
                if counts[c] + len(unit) <= self.cap and self._separation_ok(unit, c, assign):
                    assign[unit] = c
                    counts[c] += len(unit)
                    placed = True
                    if (forward and c == self.k - 1) or (not forward and c == 0):
                        forward = not forward
                        cursor = c  # S 形折返：折返处同一班连续获得两个单元
                    else:
                        cursor = (c + 1) % self.k if forward else (c - 1) % self.k
                    break
            if not placed:
                for c in range(self.k):
                    if counts[c] + len(unit) <= self.cap and self._separation_ok(unit, c, assign):
                        assign[unit] = c
                        counts[c] += len(unit)
                        placed = True
                        break
            if not placed:
                fail("班级容量不足以容纳全部学生（含同班约束单元），请提高容量或增加班级")
        self.log.event("init", classes=self.k, units=len(self.units), snake=True)
        aggs = [self._new_agg() for _ in range(self.k)]
        for unit, c in assign.items():
            self._apply(aggs[c], unit, +1)
        self._local_search(assign, counts, aggs)
        return assign

    def _separation_ok(self, unit, target_class, assign):
        if not self.pairs:
            return True
        ids = {str(self.students[i]["id"]) for i in unit}
        for other, c in assign.items():
            if c != target_class:
                continue
            other_ids = {str(self.students[i]["id"]) for i in other}
            if any((a in ids and b in other_ids) or (a in other_ids and b in ids) for a, b in self.pairs):
                return False
        return True

    # -- 局部搜索：交换保持班额不变，候选对按综合分尾部与分类维度余缺定向 --
    # 全对枚举是 O(U²)，几百人时不可用；每轮只在每个班对之间的少量定向候选里
    # 找最优改进交换，收敛质量由回归测试的均值差与构成差阈值兜底。

    def _local_search(self, assign, counts, aggs):
        max_rounds = int(self.params.get("searchRounds", 60))
        window = max(4, min(16, int(self.params.get("searchWindow", 8))))
        current = self._objective(aggs)
        for round_no in range(1, max_rounds + 1):
            by_class = [[] for _ in range(self.k)]
            class_ids = [set() for _ in range(self.k)]
            for unit, c in assign.items():
                by_class[c].append(unit)
                class_ids[c].update(str(self.students[i]["id"]) for i in unit)
            for group in by_class:
                group.sort(key=lambda unit: str(self.students[unit[0]]["id"]))
            best = None  # (delta, ua, ub)
            for ca in range(self.k):
                for cb in range(ca + 1, self.k):
                    base_pair = self._agg_cost(aggs[ca]) + self._agg_cost(aggs[cb])
                    for ua, ub in self._swap_candidates(by_class[ca], by_class[cb], aggs[ca], aggs[cb], window):
                        if len(ua) != len(ub):
                            continue  # 等额分班：只交换同规模单元，各班人数保持初解的 ±1
                        if not self._swap_ok(ua, ub, ca, cb, class_ids):
                            continue
                        self._apply(aggs[ca], ua, -1)
                        self._apply(aggs[ca], ub, +1)
                        self._apply(aggs[cb], ub, -1)
                        self._apply(aggs[cb], ua, +1)
                        moved = self._agg_cost(aggs[ca]) + self._agg_cost(aggs[cb])
                        self._apply(aggs[ca], ua, +1)
                        self._apply(aggs[ca], ub, -1)
                        self._apply(aggs[cb], ub, +1)
                        self._apply(aggs[cb], ua, -1)
                        d = moved - base_pair
                        if d < -1e-12 and (best is None or d < best[0]):
                            best = (d, ua, ub)
            if best is None:
                self.log.event("converged", rounds=round_no - 1, objective=round(current, 8))
                break
            delta, ua, ub = best
            ca, cb = assign[ua], assign[ub]
            self._apply(aggs[ca], ua, -1)
            self._apply(aggs[ca], ub, +1)
            self._apply(aggs[cb], ub, -1)
            self._apply(aggs[cb], ua, +1)
            assign[ua], assign[ub] = cb, ca
            counts[ca] += len(ub) - len(ua)
            counts[cb] += len(ua) - len(ub)
            current += delta
            self.log.event("move", round=round_no, kind="swap",
                           who=[str(self.students[ua[0]]["id"]), str(self.students[ub[0]]["id"])],
                           delta=round(delta, 8), objective=round(current, 8))
        else:
            self.log.event("round_limit", rounds=max_rounds, objective=round(current, 8))
        return assign

    def _swap_ok(self, ua, ub, ca, cb, class_ids):
        """交换后回避约束检查：ua 落到 cb、ub 落到 ca，互不算冲突。"""
        ub_ids = {str(self.students[i]["id"]) for i in ub}
        ua_ids = {str(self.students[i]["id"]) for i in ua}
        for i in ua:
            for p in self.pairs_of.get(str(self.students[i]["id"]), ()):
                if p in class_ids[cb] and p not in ub_ids:
                    return False
        for i in ub:
            for p in self.pairs_of.get(str(self.students[i]["id"]), ()):
                if p in class_ids[ca] and p not in ua_ids:
                    return False
        return True

    def _swap_candidates(self, units_a, units_b, agg_a, agg_b, window):
        """定向候选：综合分头/尾 window 名 + 每个分类维度上班 A 富余而班 B 不足（或反之）
        的取值携带者，覆盖数值均值与类别构成两类失衡的修复方向。"""
        set_a, set_b = set(units_a), set(units_b)
        def comp_sorted(units):
            return sorted(units, key=lambda u: (self.unit_score[u], str(self.students[u[0]]["id"])))

        def tails(units):
            ordered = comp_sorted(units)
            out = list(ordered[:window]) + list(ordered[-window:])
            return out

        cands_a, cands_b = set(tails(units_a)), set(tails(units_b))

        def value_of(unit, field):
            raw = self.students[unit[0]].get(field)
            if field == "gender":
                return normalize_gender(raw)
            return str(raw).strip() if raw is not None and str(raw).strip() != "" else None

        for d in self.dims:
            if d["kind"] != "categorical":
                continue
            field, values = d["field"], d["values"]
            total_a = sum(agg_a["cat"][field].values()) or 1
            total_b = sum(agg_b["cat"][field].values()) or 1
            for v in values:
                diff = agg_a["cat"][field][v] / total_a - agg_b["cat"][field][v] / total_b
                if abs(diff) < 1e-9:
                    continue
                excess_side, deficit_side = (units_a, units_b) if diff > 0 else (units_b, units_a)
                excess = [u for u in excess_side if value_of(u, field) == v][:window]
                deficit = [u for u in deficit_side if value_of(u, field) != v][:window]
                for u in excess + deficit:
                    (cands_a if u in set_a else cands_b).add(u)
        return [(a, b) for a in sorted(cands_a, key=lambda u: str(self.students[u[0]]["id"]))
                for b in sorted(cands_b, key=lambda u: str(self.students[u[0]]["id"])) if a != b]


# ---------------------------------------------------------------- 分层模式

def standardize_vectors(students, fields):
    columns, stats = [], []
    for f in fields:
        vals = []
        for s in students:
            v = to_float((s.get("assessment") or {}).get(f))
            vals.append(v)
        present = [v for v in vals if v is not None]
        m = mean(present) if present else 0.0
        sd = pstdev(present) if len(present) > 1 else 1.0
        stats.append({"field": f, "mean": m, "std": sd or 1.0, "missing": len(vals) - len(present)})
        columns.append([(v if v is not None else m) for v in vals])
    vectors = [tuple(col[i] / stats[j]["std"] for j, col in enumerate(columns)) for i in range(len(students))]
    return vectors, stats


def kmeans(vectors, k, rng, max_iter=100):
    """k-means++ 初始化 + Lloyd 迭代；空簇用最远点重启，全部决策确定。"""
    n = len(vectors)
    dim = len(vectors[0]) if vectors else 0
    if k <= 1:
        return [0] * n, [[mean([v[c] for v in vectors]) for c in range(dim)]] if vectors else [[]]
    centroids = [list(vectors[rng.randrange(n)])]
    while len(centroids) < k:
        dists = []
        for v in vectors:
            dists.append(min(sum((v[c] - centroid[c]) ** 2 for c in range(dim)) for centroid in centroids))
        total = sum(dists)
        if total <= 0:
            centroids.append(list(vectors[len(centroids) % n]))
            continue
        pick, acc = rng.random() * total, 0.0
        for i, d in enumerate(dists):
            acc += d
            if acc >= pick:
                centroids.append(list(vectors[i]))
                break
        else:
            centroids.append(list(vectors[-1]))
    labels = [0] * n
    for _ in range(max_iter):
        changed = False
        for i, v in enumerate(vectors):
            best_label, best_dist = 0, float("inf")
            for ci, centroid in enumerate(centroids):
                d = sum((v[c] - centroid[c]) ** 2 for c in range(dim))
                if d < best_dist or (d == best_dist and ci < best_label):
                    best_label, best_dist = ci, d
            if labels[i] != best_label:
                labels[i] = best_label
                changed = True
        for ci in range(k):
            rows = [vectors[i] for i in range(n) if labels[i] == ci]
            if rows:
                centroids[ci] = [mean([r[c] for r in rows]) for c in range(dim)]
            else:
                far, far_dist = 0, -1.0
                for i, v in enumerate(vectors):
                    centroid = centroids[labels[i]]
                    d = sum((v[c] - centroid[c]) ** 2 for c in range(dim))
                    if d > far_dist:
                        far, far_dist = i, d
                labels[far] = ci
                centroids[ci] = list(vectors[far])
                changed = True
        if not changed:
            break
    return labels, centroids


def largest_remainder(total, weights):
    """把 total 个名额按 weights 比例分配（最大余数法，平局按序号）。"""
    w_sum = sum(weights)
    if w_sum <= 0 or total <= 0:
        return [0] * len(weights)
    raw = [total * w / w_sum for w in weights]
    base = [int(x) for x in raw]
    rest = total - sum(base)
    for c in sorted(range(len(weights)), key=lambda c: (-(raw[c] - base[c]), c))[: max(rest, 0)]:
        base[c] += 1
    return base


class TieredSolver:
    """分层分班：画像 k-means 分层 → 方向志愿按层名额分配 → 层内按成绩性别蛇形组班。"""

    def __init__(self, students, params, seed, log):
        self.students = students
        self.params = params
        self.rng = random.Random(seed)
        self.log = log
        self.k = int(params.get("classCount") or 0)
        self.cap = int(params["capacityPerClass"])
        self.layer_count = max(1, int(params.get("layerCount", 3)))
        self.fields = self._assessment_fields()
        self.vectors, self.field_stats = standardize_vectors(students, self.fields)
        self.constraints = params.get("constraints", [])
        self.layer_name = lambda r: chr(ord("A") + r) if self.layer_count > 1 else None

    def _assessment_fields(self):
        fields = self.params.get("assessmentFields")
        if fields:
            fields = [str(f) for f in fields]
            if not fields:
                fail("assessmentFields 不能为空")
            return fields
        found = set()
        for s in self.students:
            a = s.get("assessment") or {}
            for f, v in a.items():
                if to_float(v) is not None:
                    found.add(str(f))
        if not found:
            fail("分层模式需要测评画像字段：请在 params.assessmentFields 指定，或让学生携带 assessment 数值字段")
        return sorted(found)

    def solve(self):
        students, n = self.students, len(self.students)
        labels, centroids = kmeans(self.vectors, self.layer_count, self.rng)
        order = sorted(range(self.layer_count), key=lambda c: (-sum(x * x for x in centroids[c]), c))
        rank_of = {c: r for r, c in enumerate(order)}
        student_layer = [rank_of[labels[i]] for i in range(n)]
        layer_sizes = [sum(1 for x in student_layer if x == r) for r in range(self.layer_count)]
        self.log.event("cluster", layers=self.layer_count, sizes=layer_sizes, fields=self.fields)

        directions = self._directions()
        dir_cap = {d["name"]: int(d["classCount"]) * self.cap for d in directions}
        if self.k and sum(int(d["classCount"]) for d in directions) != self.k:
            fail(f"方向班级总数 {sum(int(d['classCount']) for d in directions)} 与 classCount={self.k} 不一致")

        # 各方向层名额 = 方向容量 × 全局层占比（最大余数法）
        dir_layer_quota = {d["name"]: largest_remainder(dir_cap[d["name"]], layer_sizes) for d in directions}
        used = {d["name"]: [0] * self.layer_count for d in directions}

        # 志愿分配：固定随机序，逐生按志愿顺序申请（方向, 所在层）名额
        order_idx = sorted(range(n), key=lambda i: (0 if (students[i].get("preference") or []) else 1, self.rng.random()))
        direction_of = [None] * n
        granted, unmet = {}, {}
        for i in order_idx:
            prefs = [str(p).strip() for p in (students[i].get("preference") or []) if str(p).strip()]
            if not prefs:
                continue
            layer = student_layer[i]
            for rank_no, p in enumerate(prefs, start=1):
                if p in dir_layer_quota and used[p][layer] < dir_layer_quota[p][layer]:
                    direction_of[i] = p
                    granted[i] = rank_no
                    used[p][layer] += 1
                    break
            if direction_of[i] is None:
                reasons = []
                for p in dict.fromkeys(prefs):
                    if p not in dir_layer_quota:
                        reasons.append(f"{p}：不在本次分班方向表中")
                        continue
                    layer_left = dir_layer_quota[p][layer] - used[p][layer]
                    total_left = dir_cap[p] - sum(used[p])
                    if total_left <= 0:
                        reasons.append(f"{p}：班级容量已满")
                    elif layer_left <= 0:
                        reasons.append(f"{p}：{self.layer_name(layer)} 层名额已满（画像分布不匹配）")
                unmet[i] = "；".join(reasons) or "志愿未能满足"
        # 未满足且未落位的学生：按所在层剩余名额最宽的方向收容（留痕，计为未满足志愿）
        for i in sorted((i for i in range(n) if direction_of[i] is None), key=lambda i: str(students[i]["id"])):
            layer = student_layer[i]
            roomy = max(dir_layer_quota, key=lambda p: (dir_layer_quota[p][layer] - used[p][layer], [-used[p][r] for r in range(self.layer_count)], p))
            if dir_layer_quota[roomy][layer] - used[roomy][layer] <= 0:
                roomy = max(dir_layer_quota, key=lambda p: (dir_cap[p] - sum(used[p]), p))
            direction_of[i] = roomy
            used[roomy][layer] += 1
            if i not in unmet:
                unmet[i] = "未填报方向志愿（按所在层剩余名额收容）"
            self.log.event("fallback_placed", student=str(students[i]["id"]), direction=roomy, layer=self.layer_name(layer))

        # 方向内组班：按层人数从大到小装箱——整层优先独占班级，装不下的余量并入
        # 有余位的班（混班留痕），容量是硬约束；报名总量已在名额环节受方向容量限制。
        class_assign = [None] * n
        class_meta = []
        for d in directions:
            name = d["name"]
            n_classes = int(d["classCount"])
            members = [i for i in range(n) if direction_of[i] == name]
            if not members:
                continue
            by_layer = {r: sorted((i for i in members if student_layer[i] == r), key=lambda i: str(students[i]["id"]))
                        for r in range(self.layer_count)}
            groups = []  # 每班 {layers: set, ids: []}
            for r in sorted(range(self.layer_count), key=lambda r: (-len(by_layer.get(r, [])), r)):
                pending = list(by_layer.get(r, []))
                if not pending:
                    continue
                need = -(-len(pending) // self.cap)
                dedicated = min(need, n_classes - len(groups))
                mixed = 0
                if dedicated > 0:
                    placed_ids = set()
                    for part in self._split_evenly(pending, dedicated):
                        if len(part) > self.cap:  # dedicated 被班级余量截断时，超出部分转入混班
                            part = part[: self.cap]
                        groups.append({"layers": {r}, "ids": part})
                        placed_ids.update(part)
                    pending = [i for i in pending if i not in placed_ids]
                # 余量（无整班可开或容量截断）轮转摊入有余位的班级，并留痕
                gi = 0
                while pending:
                    rooms = [x for x in range(len(groups)) if self.cap - len(groups[x]["ids"]) > 0]
                    if not rooms:
                        fail(f"方向 {name} 层 {self.layer_name(r)} 无法在容量内装下，请检查方向班级数")
                    target = rooms[gi % len(rooms)]
                    groups[target]["ids"].append(pending.pop(0))
                    groups[target]["layers"].add(r)
                    mixed += 1
                    gi += 1
                if mixed:
                    self.log.event("layer_mixed", direction=name, layer=self.layer_name(r), mixed=mixed)
            for gi, group in enumerate(groups):
                layer_desc = "+".join(self.layer_name(x) for x in sorted(group["layers"])) if self.layer_count > 1 else None
                cid = len(class_meta)
                class_meta.append({"id": f"C{cid + 1:02d}", "label": f"{name}{gi + 1:02d}班", "direction": name,
                                   "layer": layer_desc, "capacity": self.cap})
                for i in group["ids"]:
                    class_assign[i] = cid

        constraint_results = self._apply_same_class(class_meta, class_assign)
        return {"student_layer": student_layer, "layer_sizes": layer_sizes, "class_meta": class_meta,
                "class_assign": class_assign, "direction_of": direction_of, "granted": granted, "unmet": unmet,
                "dir_layer_quota": dir_layer_quota, "used": used, "constraint_results": constraint_results}

    def _directions(self):
        directions = self.params.get("directions")
        if directions:
            out = []
            names = set()
            for d in directions:
                name = str(d.get("name") or "").strip()
                if not name or name in names:
                    fail("directions 名称缺失或重复")
                if int(d.get("classCount", 0)) <= 0:
                    fail(f"方向 {name} 的 classCount 必须为正")
                names.add(name)
                out.append({"name": name, "classCount": int(d["classCount"])})
            return sorted(out, key=lambda d: d["name"])
        prefs = []
        for s in self.students:
            for p in s.get("preference") or []:
                p = str(p).strip()
                if p and p not in prefs:
                    prefs.append(p)
        if not prefs or not self.k:
            fail("分层模式需要方向定义：在 params.directions 给出方向与班级数（或同时给出 classCount 按志愿需求自动分配）")
        demand = {p: 0 for p in prefs}
        for s in self.students:
            plist = s.get("preference") or []
            if plist:
                first = str(plist[0]).strip()
                demand[first] = demand.get(first, 0) + 1
        quota = largest_remainder(self.k, [demand.get(p, 0) for p in prefs])
        quota = [max(1, q) for q in quota]
        while sum(quota) > self.k and max(quota) > 1:
            quota[quota.index(max(quota))] -= 1
        self.log.event("directions_auto", demand=demand, classes=dict(zip(prefs, quota)))
        return [{"name": p, "classCount": q} for p, q in sorted(zip(prefs, quota))]

    def _split_evenly(self, ids, groups_count):
        """层内按成绩降序蛇形铺班、性别轮转穿插，确定性。"""
        def score_key(i):
            v = to_float(self.students[i].get("score"))
            return v if v is not None else float("-inf")
        queues = [[], [], []]
        for i in sorted(ids, key=lambda i: (normalize_gender(self.students[i].get("gender")) is None, str(self.students[i]["id"]))):
            g = {"男": 0, "女": 1}.get(normalize_gender(self.students[i].get("gender")), 2)
            queues[g].append(i)
        buckets = [[] for _ in range(groups_count)]
        cursor, forward = 0, True
        for queue in queues:
            for i in sorted(queue, key=lambda i: (-score_key(i), str(self.students[i]["id"]))):
                buckets[cursor].append(i)
                if (forward and cursor == groups_count - 1) or (not forward and cursor == 0):
                    forward = not forward
                else:
                    cursor = cursor + 1 if forward else cursor - 1
        return [sorted(b, key=lambda i: str(self.students[i]["id"])) for b in buckets]

    def _apply_same_class(self, class_meta, class_assign):
        """分层模式下的同班约束：容量允许时统一到组内首个学生所在班，否则如实报告未满足。"""
        index = {str(s["id"]): i for i, s in enumerate(self.students)}
        results = []
        for c in self.constraints:
            ctype = c.get("type")
            ids = [str(x) for x in c.get("students", [])]
            if any(x not in index for x in ids):
                fail(f"约束引用了不存在的学生：{ids}")
            if ctype == "same-class":
                target = class_assign[index[ids[0]]]
                ok = True
                for x in ids[1:]:
                    if class_assign[index[x]] != target:
                        if sum(1 for cc in class_assign if cc == target) < class_meta[target]["capacity"]:
                            class_assign[index[x]] = target
                            self.log.event("constraint_unify", constraint=ids, moved=x, to_class=class_meta[target]["label"])
                        else:
                            ok = False
                results.append({"type": ctype, "students": ids, "reason": c.get("reason", ""),
                                "satisfied": bool(ok), "note": "" if ok else "目标班容量不足，无法同班，请人工复核"})
            elif ctype == "different-class":
                ok = len({class_assign[index[x]] for x in ids}) == len(ids) if len(ids) == 2 else False
                results.append({"type": ctype, "students": ids, "reason": c.get("reason", ""), "satisfied": bool(ok),
                                "note": "" if ok else "分层组班后仍在同一班，请人工调整或重新求解"})
        return results


# ---------------------------------------------------------------- 输出

def field_completeness(students):
    report = {}
    for field in KNOWN_FIELDS:
        present = 0
        for s in students:
            v = s.get(field)
            if field == "assessment":
                present += 1 if isinstance(v, dict) and any(to_float(x) is not None for x in v.values()) else 0
            elif field == "preference":
                present += 1 if isinstance(v, list) and any(str(p).strip() for p in v) else 0
            else:
                present += 1 if v is not None and str(v).strip() != "" else 0
        report[field] = {"present": present, "missing": len(students) - present, "total": len(students)}
    return report


def write_rosters(out_dir, students, class_meta, class_assign, tiered_ctx=None):
    roster_dir = out_dir / "roster"
    roster_dir.mkdir(parents=True, exist_ok=True)
    header = ["序号", "班级", "学号或编号", "姓名", "性别", "生源地区", "成绩"]
    if tiered_ctx:
        header += ["方向", "层次", "志愿满足"]
    all_rows = []
    for cid, meta in enumerate(class_meta):
        ids = sorted((i for i, c in enumerate(class_assign) if c == cid), key=lambda i: str(students[i]["id"]))
        rows = []
        for seq, i in enumerate(ids, start=1):
            s = students[i]
            row = {"序号": seq, "班级": meta["label"], "学号或编号": s.get("id"), "姓名": s.get("name", ""),
                   "性别": normalize_gender(s.get("gender")) or "", "生源地区": s.get("region", ""), "成绩": s.get("score", "")}
            if tiered_ctx:
                row["方向"] = meta.get("direction", "")
                row["层次"] = meta.get("layer") or ""
                rank = tiered_ctx["granted"].get(i)
                row["志愿满足"] = f"第{rank}志愿" if rank else ("未填报志愿" if i in tiered_ctx["no_pref"] else "未满足")
            rows.append(row)
            all_rows.append(row)
        safe = "".join(ch if (ch.isalnum() or ch in "-_") else "_" for ch in meta["label"]).strip("_") or meta["id"]
        _write_csv(roster_dir / f"{meta['id']}-{safe}.csv", header, rows)
    _write_csv(roster_dir / "roster-all.csv", header, all_rows)
    return roster_dir


def _write_csv(path, header, rows):
    with path.open("w", encoding="utf-8-sig", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=header, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def class_stats(students, class_meta, class_assign, tiered_ctx=None):
    stats = []
    for cid, meta in enumerate(class_meta):
        ids = [i for i, c in enumerate(class_assign) if c == cid]
        entry = {"id": meta["id"], "label": meta["label"], "count": len(ids), "capacity": meta["capacity"]}
        genders = {}
        for i in ids:
            g = normalize_gender(students[i].get("gender")) or "未填写"
            genders[g] = genders.get(g, 0) + 1
        entry["genderCounts"] = genders
        vals, _ = numeric_column([students[i] for i in ids], "score")
        entry["score"] = {"mean": round(mean(vals), 2), "std": round(pstdev(vals), 2),
                          "min": min(vals) if vals else None, "max": max(vals) if vals else None, "missing": len(ids) - len(vals)}
        regions = {}
        for i in ids:
            r = str(students[i].get("region") or "").strip()
            if r:
                regions[r] = regions.get(r, 0) + 1
        entry["regionTop"] = [{"region": r, "count": c} for r, c in sorted(regions.items(), key=lambda kv: (-kv[1], kv[0]))[:5]]
        if tiered_ctx:
            entry["direction"] = meta.get("direction")
            entry["layer"] = meta.get("layer")
            profile = {}
            for f in tiered_ctx["fields"]:
                fv = [to_float((students[i].get("assessment") or {}).get(f)) for i in ids]
                fv = [v for v in fv if v is not None]
                profile[f] = round(mean(fv), 2) if fv else None
            entry["assessmentProfile"] = profile
            entry["preferenceGranted"] = sum(1 for i in ids if i in tiered_ctx["granted"])
        stats.append(entry)
    return stats


def balance_report(students, class_meta, class_assign, dims):
    members = [[] for _ in class_meta]
    for i, c in enumerate(class_assign):
        members[c].append(i)
    out = {"dimensions": []}
    for d in dims:
        if d["kind"] == "numeric":
            means = [round(mean(numeric_column([students[i] for i in g], d["field"])[0]), 4) for g in members]
            present = [m for m in means if m is not None]
            out["dimensions"].append({"field": d["field"], "kind": "numeric", "weight": round(d["weight"], 4),
                                      "classMeans": means,
                                      "meanDiff": round(max(present) - min(present), 4) if present else None,
                                      "globalStd": round(d["std"], 4), "missing": d["missing"]})
        else:
            values = d["values"]
            shares = []
            for g in members:
                vals, _ = categorical_column([students[i] for i in g], d["field"])
                counts = {}
                for v in vals:
                    counts[v] = counts.get(v, 0) + 1
                shares.append({v: round(counts.get(v, 0) / len(vals), 4) if vals else None for v in values})
            out["dimensions"].append({"field": d["field"], "kind": "categorical", "weight": round(d["weight"], 4),
                                      "classShares": shares, "missing": d["missing"],
                                      "maxShareGap": {v: round(max(s[v] for s in shares if s[v] is not None) -
                                                              min(s[v] for s in shares if s[v] is not None), 4) for v in values}})
    within = [pstdev(numeric_column([students[i] for i in g], "score")[0]) for g in members]
    within = [s for s in within if s]
    all_vals, _ = numeric_column(students, "score")
    out["heterogeneity"] = {"withinClassStdAvg": round(mean(within), 4) if within else None,
                            "globalStd": round(pstdev(all_vals), 4),
                            "note": "班内成绩标准差接近总体标准差表示班内保持高/中/低混合，未出现能力分层沉淀"}
    return out


def preference_report(students, solver, result):
    n = len(students)
    granted, unmet = result["granted"], result["unmet"]
    by_rank = {}
    for r in granted.values():
        by_rank[r] = by_rank.get(r, 0) + 1
    unmet_counts = {}
    for reason in unmet.values():
        key = ("班级容量" if "容量" in reason else "画像分布" if "层名额" in reason else "未填报志愿" if "未填报" in reason else "其他")
        unmet_counts[key] = unmet_counts.get(key, 0) + 1
    return {"total": n, "granted": len(granted), "grantedRate": round(len(granted) / n, 4),
            "byRank": {str(r): c for r, c in sorted(by_rank.items())}, "unmetCounts": unmet_counts,
            "unmetDetail": [{"studentId": str(students[i]["id"]), "reason": reason}
                            for i, reason in sorted(unmet.items(), key=lambda kv: str(students[kv[0]]["id"]))],
            "layers": [{"layer": solver.layer_name(r), "count": result["layer_sizes"][r]} for r in range(solver.layer_count)],
            "directionQuota": {p: {"capacity": sum(result["dir_layer_quota"][p]),
                                   "byLayer": {solver.layer_name(r): result["dir_layer_quota"][p][r] for r in range(solver.layer_count)},
                                   "used": {solver.layer_name(r): result["used"][p][r] for r in range(solver.layer_count)}}
                               for p in result["dir_layer_quota"]}}


def load_students(path: Path):
    data = json.loads(path.read_text(encoding="utf-8"))
    students = data.get("students") if isinstance(data, dict) else data
    if not isinstance(students, list) or not students:
        fail("students.json 必须包含非空 students 数组")
    seen = set()
    for i, s in enumerate(students):
        if not isinstance(s, dict):
            fail(f"第 {i + 1} 名学生不是对象")
        sid = str(s.get("id") or "").strip()
        if not sid:
            fail(f"第 {i + 1} 名学生缺少 id")
        if sid in seen:
            fail(f"学生编号重复：{sid}")
        seen.add(sid)
    return students


def main():
    ap = argparse.ArgumentParser(description="智能分班确定性求解器")
    ap.add_argument("params", type=Path)
    ap.add_argument("students", type=Path)
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--state", type=Path, default=Path("output/placement-state.json"))
    ap.add_argument("--fresh-state", action="store_true", help="跳过重掷链校验（复现结果或演示时使用）")
    args = ap.parse_args()

    try:
        params = json.loads(args.params.read_text(encoding="utf-8"))
        students = load_students(args.students)
    except OSError as exc:
        fail(f"无法读取输入文件：{exc}")
    except json.JSONDecodeError as exc:
        fail(f"输入文件不是合法 JSON：{exc}")

    mode = params.get("mode")
    if mode not in ("balanced", "tiered"):
        fail("params.mode 必须是 balanced（均衡）或 tiered（分层）")
    k = int(params.get("classCount") or 0)
    cap = int(params.get("capacityPerClass") or 0)
    if mode == "balanced" and k <= 0:
        fail("均衡模式必须给出 classCount（班级数量）")
    if cap <= 0:
        fail("必须给出 capacityPerClass（每班容量上限）")
    if k and k * cap < len(students):
        fail(f"总容量 {k * cap} 小于学生数 {len(students)}")

    params_hash = sha256_text(canonical({k: v for k, v in params.items() if k != "attempt"}))
    students_hash = sha256_text(canonical(students))
    fingerprint = sha256_text(params_hash + students_hash)
    attempt = int(params.get("attempt", 1))
    if attempt not in (1, 2):
        fail("attempt 只能为 1（首次求解）或 2（一次受控重掷）")

    seed_input = params.get("seed")
    if seed_input is None:
        base_seed = int(fingerprint[:16], 16)
    else:
        base_seed = int(seed_input) if str(seed_input).isdigit() else int(str(seed_input).encode("utf-8").hex()[:15], 16)
    effective_seed = base_seed if attempt == 1 else int(sha256_text(f"{base_seed}#attempt2")[:16], 16)

    state = {"runs": []}
    if not args.fresh_state:
        if args.state.exists():
            try:
                state = json.loads(args.state.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError):
                fail(f"状态文件损坏：{args.state}（复现请加 --fresh-state）")
        same = [r for r in state.get("runs", []) if r.get("fingerprint") == fingerprint]
        if attempt == 2 and not any(r.get("attempt") == 1 for r in same):
            fail("尚未做过首次求解，不能直接重掷：请先以 attempt=1 运行")
        if any(r.get("attempt") == 2 for r in same):
            fail("该任务已完成过一次受控重掷，不允许再次重掷；如需调整请修改参数后作为新任务求解")
        if attempt == 1 and any(r.get("attempt") == 1 for r in same):
            fail("该输入已做过首次求解；如需重掷请将 params.attempt 改为 2，复现结果请加 --fresh-state")

    args.out.mkdir(parents=True, exist_ok=True)
    audit_dir = args.out / "audit"
    audit_dir.mkdir(exist_ok=True)
    log = SolverLog(audit_dir / "solver-log.jsonl")
    log.event("start", solver=SOLVER_VERSION, mode=mode, students=len(students), attempt=attempt, seed=effective_seed)

    if mode == "balanced":
        solver = BalancedSolver(students, params, effective_seed, log)
        assign = solver.solve()
        labels = params.get("classLabels") or []
        class_meta = [{"id": f"C{i + 1:02d}", "label": str(labels[i]) if i < len(labels) else f"{i + 1}班", "capacity": cap}
                      for i in range(k)]
        class_assign = [0] * len(students)
        for unit, c in assign.items():
            for i in unit:
                class_assign[i] = c
        tiered_ctx = None
        balance = balance_report(students, class_meta, class_assign, solver.dims)
        constraints = _constraint_report(students, params, class_assign)
        preference = None
    else:
        solver = TieredSolver(students, params, effective_seed, log)
        result = solver.solve()
        class_meta, class_assign = result["class_meta"], result["class_assign"]
        if not class_meta or any(c is None for c in class_assign):
            fail("分层求解未覆盖全部学生，请检查方向与班级数设置")
        tiered_ctx = {"granted": result["granted"], "fields": solver.fields,
                      "no_pref": {i for i in range(len(students)) if not (students[i].get("preference") or [])}}
        balance = None
        constraints = result["constraint_results"]
        preference = preference_report(students, solver, result)

    roster_dir = write_rosters(args.out, students, class_meta, class_assign, tiered_ctx)
    log.event("roster_written", classes=len(class_meta), files=len(list(roster_dir.iterdir())))

    assignment_rows = []
    for i, (s, c) in enumerate(zip(students, class_assign)):
        row = {"studentId": str(s["id"]), "name": s.get("name", ""), "classId": class_meta[c]["id"], "classLabel": class_meta[c]["label"]}
        if tiered_ctx:
            row["direction"] = class_meta[c].get("direction")
            row["layer"] = class_meta[c].get("layer")
            if i in tiered_ctx["granted"]:
                row["preferenceGranted"] = f"第{tiered_ctx['granted'][i]}志愿"
            if i in result["unmet"]:
                row["unmetReason"] = result["unmet"][i]
        assignment_rows.append(row)

    result_obj = {
        "meta": {"taskTitle": params.get("taskTitle", "智能分班"), "mode": mode, "solverVersion": SOLVER_VERSION,
                 "generatedAt": time.strftime("%Y-%m-%dT%H:%M:%S%z"), "classCount": len(class_meta),
                 "capacityPerClass": cap, "studentCount": len(students)},
        "audit": {"seed": base_seed, "effectiveSeed": effective_seed, "attempt": attempt,
                  "paramsSha256": params_hash, "studentsSha256": students_hash, "inputFingerprint": fingerprint,
                  "solverLogHead": None},
        "fieldCompleteness": field_completeness(students),
        "classes": class_stats(students, class_meta, class_assign, tiered_ctx),
        "balance": balance,
        "preference": preference,
        "constraints": constraints,
        "assignment": assignment_rows,
    }
    result_path = args.out / "result.json"
    result_path.write_text(json.dumps(result_obj, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    log.event("done", result="result.json")
    result_sha = sha256_file(result_path)

    manifest = {
        "solver": SOLVER_VERSION, "mode": mode, "taskTitle": params.get("taskTitle", "智能分班"),
        "seed": base_seed, "effectiveSeed": effective_seed, "attempt": attempt,
        "paramsSha256": params_hash, "studentsSha256": students_hash, "inputFingerprint": fingerprint,
        "resultSha256": result_sha, "solverLogHead": log.head,
        "paramsFile": str(args.params), "studentsFile": str(args.students),
        "reproduceCommand": f"python3 {Path(__file__).resolve()} {args.params} {args.students} --out <空目录> --fresh-state",
        "note": "同一种子与同一输入可复现相同分班与统计（result.json 除 generatedAt 外一致）；求解日志为哈希链，事后改动会与 solverLogHead 不符",
        "generatedAt": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
    }
    (audit_dir / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    if not args.fresh_state:
        state.setdefault("runs", []).append({"fingerprint": fingerprint, "attempt": attempt, "seed": effective_seed,
                                             "outDir": str(args.out), "resultSha256": result_sha,
                                             "at": time.strftime("%Y-%m-%dT%H:%M:%S%z")})
        args.state.parent.mkdir(parents=True, exist_ok=True)
        tmp = args.state.with_suffix(".tmp")
        tmp.write_text(json.dumps(state, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        tmp.replace(args.state)

    print(json.dumps({"out": str(args.out), "classes": len(class_meta), "students": len(students),
                      "attempt": attempt, "seed": effective_seed, "balance": balance,
                      "preference": preference,
                      "constraintViolations": [c for c in constraints if not c.get("satisfied")]},
                     ensure_ascii=False, indent=2))


def _constraint_report(students, params, class_assign):
    index = {str(s["id"]): i for i, s in enumerate(students)}
    results = []
    for c in params.get("constraints", []):
        ctype = c.get("type")
        ids = [str(x) for x in c.get("students", [])]
        if any(x not in index for x in ids):
            fail(f"约束引用了不存在的学生：{ids}")
        if ctype == "same-class":
            ok = len({class_assign[index[x]] for x in ids}) <= 1
        elif ctype == "different-class":
            ok = len({class_assign[index[x]] for x in ids}) == 2 if len(ids) == 2 else False
        else:
            continue
        results.append({"type": ctype, "students": ids, "reason": c.get("reason", ""), "satisfied": bool(ok),
                        "note": "" if ok else "约束未满足，请调整容量、班级数或约束后重新求解"})
    return results


if __name__ == "__main__":
    main()
