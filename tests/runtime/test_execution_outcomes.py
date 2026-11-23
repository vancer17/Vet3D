# 文件信息：L0-04 执行事实与局部观察对账测试。
# 作用：验证尝试身份、终态边界及查询、提交、等待诊断不能冒充确认观察。
# 范围：仅使用显式构造的内存事实，不证明真实执行、远端受理或重启恢复。
"""通过公开入口验证结果语义，不实现模拟执行器或重试系统。"""

import asyncio
from dataclasses import FrozenInstanceError
from typing import cast
import unittest
from uuid import uuid4

from vet3d.execution import (
    AttemptActive, AttemptCancelled, AttemptFailed, AttemptObservation, AttemptSucceeded,
    CapabilityUnavailable, ExecutionContractError, InputInsufficient, QueryUnavailable,
    SubmissionUnconfirmed, WaitEnded, WaitEndReason, preserve_after_query_failure,
    reconcile_observation, validate_attempt_fact,
)
from vet3d.identity import AttemptId, AttemptIdentity, JobId


class ExecutionOutcomeTests(unittest.TestCase):
    """检查调用方提交的事实关系，不把夹具断言当成外部执行证据。"""

    def setUp(self) -> None:
        """准备同一作业下两个不同尝试，用于检查身份错配。"""
        job_id = JobId(uuid4())
        self.attempt = AttemptIdentity(id=AttemptId(uuid4()), job_id=job_id)
        self.other_attempt = AttemptIdentity(id=AttemptId(uuid4()), job_id=job_id)

    def test_attempt_facts_require_the_exact_resolved_attempt(self) -> None:
        """确认观察和独立诊断均需匹配原尝试，不能用同作业的其他尝试代替。"""
        facts: tuple[
            AttemptObservation | QueryUnavailable | SubmissionUnconfirmed | WaitEnded, ...
        ] = (
            AttemptActive(self.attempt.id),
            AttemptSucceeded(self.attempt.id),
            AttemptFailed(self.attempt.id, reason="执行器报告失败"),
            AttemptCancelled(self.attempt.id),
            QueryUnavailable(self.attempt.id, reason="查询连接中断"),
            SubmissionUnconfirmed(self.attempt.id, reason="未取得受理回执"),
            WaitEnded(self.attempt.id, reason=WaitEndReason.DEADLINE),
            WaitEnded(self.attempt.id, reason=WaitEndReason.CANCEL_REQUESTED),
        )
        for fact in facts:
            with self.subTest(fact=fact):
                validate_attempt_fact(fact, attempt=self.attempt)
                with self.assertRaises(ExecutionContractError):
                    validate_attempt_fact(fact, attempt=self.other_attempt)

    def test_fact_fields_reject_wrong_identity_and_wait_reason_types(self) -> None:
        """底层 UUID 相同也不能混用作业身份，等待原因不能用裸字符串替代。"""
        wrong_id = cast(AttemptId, JobId(self.attempt.id.value))
        with self.assertRaises(TypeError):
            AttemptActive(wrong_id)
        with self.assertRaises(TypeError):
            AttemptFailed(wrong_id, reason="失败")
        with self.assertRaises(TypeError):
            QueryUnavailable(wrong_id, reason="查询失败")
        with self.assertRaises(TypeError):
            SubmissionUnconfirmed(wrong_id, reason="提交不明")
        with self.assertRaises(TypeError):
            WaitEnded(self.attempt.id, reason=cast(WaitEndReason, "deadline"))
        with self.assertRaises(TypeError):
            validate_attempt_fact(AttemptActive(self.attempt.id), attempt=cast(AttemptIdentity, self.attempt.id))

    def test_diagnostic_reasons_reject_missing_or_invalid_text(self) -> None:
        """原因必须是非空白 UTF-8 文字，不以隐式转换或空消息补齐事实。"""
        for reason in ("", " \t\n", "失效\ud800"):
            with self.subTest(reason=repr(reason)):
                with self.assertRaises(ExecutionContractError):
                    AttemptFailed(self.attempt.id, reason=reason)
                with self.assertRaises(ExecutionContractError):
                    QueryUnavailable(self.attempt.id, reason=reason)
                with self.assertRaises(ExecutionContractError):
                    SubmissionUnconfirmed(self.attempt.id, reason=reason)
        with self.assertRaises(TypeError):
            AttemptFailed(self.attempt.id, reason=cast(str, 5))
        with self.assertRaises(TypeError):
            QueryUnavailable(self.attempt.id, reason=cast(str, None))

    def test_confirmed_and_diagnostic_facts_are_frozen(self) -> None:
        """记录不能原地更换尝试或把诊断改写为新的结果依据。"""
        failed = AttemptFailed(self.attempt.id, reason="已确认失败")
        waiting = WaitEnded(self.attempt.id, reason=WaitEndReason.DEADLINE)
        with self.assertRaises(FrozenInstanceError):
            setattr(failed, "attempt_id", self.other_attempt.id)
        with self.assertRaises(FrozenInstanceError):
            setattr(failed, "reason", "另一份诊断")
        with self.assertRaises(FrozenInstanceError):
            setattr(waiting, "reason", WaitEndReason.CANCEL_REQUESTED)

    def test_first_confirmed_observation_does_not_require_a_fabricated_active_record(self) -> None:
        """首次查到终态可直接保留，不要求补造此前活动状态。"""
        observations: tuple[AttemptObservation, ...] = (
            AttemptActive(self.attempt.id), AttemptSucceeded(self.attempt.id),
            AttemptFailed(self.attempt.id, reason="首次取得失败报告"), AttemptCancelled(self.attempt.id),
        )
        for current in observations:
            with self.subTest(current=current):
                self.assertIs(reconcile_observation(None, current), current)

    def test_active_observation_can_continue_or_reach_any_confirmed_terminal(self) -> None:
        """活动尝试可以继续活动或由执行端确认成功、失败或取消。"""
        last = AttemptActive(self.attempt.id)
        observations: tuple[AttemptObservation, ...] = (
            AttemptActive(self.attempt.id), AttemptSucceeded(self.attempt.id),
            AttemptFailed(self.attempt.id, reason="执行端确认失败"), AttemptCancelled(self.attempt.id),
        )
        for current in observations:
            with self.subTest(current=current):
                self.assertIs(reconcile_observation(last, current), current)

    def test_same_terminal_category_accepts_new_confirmed_diagnostics(self) -> None:
        """同类终态允许按调用方确认的顺序更新诊断，不把原因文本变化当终态矛盾。"""
        pairs: tuple[tuple[AttemptObservation, AttemptObservation], ...] = (
            (AttemptSucceeded(self.attempt.id), AttemptSucceeded(self.attempt.id)),
            (AttemptCancelled(self.attempt.id), AttemptCancelled(self.attempt.id)),
            (
                AttemptFailed(self.attempt.id, reason="初次失败诊断"),
                AttemptFailed(self.attempt.id, reason="  后续补充的详细失败诊断\n"),
            ),
        )
        for last, current in pairs:
            with self.subTest(last=last, current=current):
                self.assertIs(reconcile_observation(last, current), current)

    def test_confirmed_terminal_cannot_regress_or_change_category(self) -> None:
        """可信终态不能回到活动，也不能改成另一种可信终态。"""
        terminals: tuple[AttemptObservation, ...] = (
            AttemptSucceeded(self.attempt.id), AttemptFailed(self.attempt.id, reason="失败"),
            AttemptCancelled(self.attempt.id),
        )
        for last in terminals:
            with self.subTest(last=last, current="活动"):
                with self.assertRaises(ExecutionContractError):
                    reconcile_observation(last, AttemptActive(self.attempt.id))
            for current in terminals:
                if type(last) is not type(current):
                    with self.subTest(last=last, current=current):
                        with self.assertRaises(ExecutionContractError):
                            reconcile_observation(last, current)

    def test_reconciliation_rejects_another_attempt_even_when_category_matches(self) -> None:
        """同一作业下的新尝试不能覆盖原尝试的活动或终态观察。"""
        with self.assertRaises(ExecutionContractError):
            reconcile_observation(AttemptActive(self.attempt.id), AttemptActive(self.other_attempt.id))
        with self.assertRaises(ExecutionContractError):
            reconcile_observation(AttemptSucceeded(self.attempt.id), AttemptSucceeded(self.other_attempt.id))

    def test_query_failure_preserves_the_original_observation_or_absence(self) -> None:
        """查询失败原样保留 last；没有可信观察时不补造活动或失败状态。"""
        failure = QueryUnavailable(self.attempt.id, reason="查询暂不可用")
        previous: tuple[AttemptObservation | None, ...] = (
            None, AttemptActive(self.attempt.id), AttemptSucceeded(self.attempt.id),
            AttemptFailed(self.attempt.id, reason="此前已确认失败"), AttemptCancelled(self.attempt.id),
        )
        for last in previous:
            with self.subTest(last=last):
                self.assertIs(
                    preserve_after_query_failure(last, failure=failure, attempt=self.attempt), last,
                )

    def test_query_failure_rejects_mismatched_query_or_previous_observation(self) -> None:
        """查询诊断和已有观察都必须属于明确传入的原尝试。"""
        with self.assertRaises(ExecutionContractError):
            preserve_after_query_failure(
                None,
                failure=QueryUnavailable(self.other_attempt.id, reason="其他尝试的查询失败"),
                attempt=self.attempt,
            )
        with self.assertRaises(ExecutionContractError):
            preserve_after_query_failure(
                AttemptSucceeded(self.other_attempt.id),
                failure=QueryUnavailable(self.attempt.id, reason="本次查询失败"),
                attempt=self.attempt,
            )

    def test_query_submission_and_wait_diagnostics_are_not_confirmed_observations(self) -> None:
        """独立诊断不能替代确认观察，也不能借用查询失败入口改变已有结果。"""
        diagnostics: tuple[object, ...] = (
            QueryUnavailable(self.attempt.id, reason="查询无结果"),
            SubmissionUnconfirmed(self.attempt.id, reason="受理结果不明"),
            WaitEnded(self.attempt.id, reason=WaitEndReason.DEADLINE),
            WaitEnded(self.attempt.id, reason=WaitEndReason.CANCEL_REQUESTED),
            asyncio.CancelledError(), TimeoutError("调用等待超时"),
        )
        for diagnostic in diagnostics:
            with self.subTest(diagnostic=diagnostic):
                with self.assertRaises(TypeError):
                    reconcile_observation(None, cast(AttemptObservation, diagnostic))
                with self.assertRaises(TypeError):
                    reconcile_observation(cast(AttemptObservation, diagnostic), AttemptActive(self.attempt.id))
        with self.assertRaises(TypeError):
            preserve_after_query_failure(
                AttemptActive(self.attempt.id),
                failure=cast(QueryUnavailable, SubmissionUnconfirmed(self.attempt.id, reason="受理不明")),
                attempt=self.attempt,
            )

    def test_wait_end_does_not_authorize_replacing_the_original_attempt(self) -> None:
        """期限或取消请求只结束等待，不能据此把新尝试观察合入原尝试。"""
        last = AttemptActive(self.attempt.id)
        for reason in WaitEndReason:
            with self.subTest(reason=reason):
                wait = WaitEnded(self.attempt.id, reason=reason)
                validate_attempt_fact(wait, attempt=self.attempt)
                with self.assertRaises(TypeError):
                    reconcile_observation(last, cast(AttemptObservation, wait))
                with self.assertRaises(ExecutionContractError):
                    reconcile_observation(last, AttemptActive(self.other_attempt.id))

    def test_execution_preconditions_do_not_fabricate_an_attempt_fact(self) -> None:
        """缺少能力或输入可在执行前表达，但不能当作某个尝试的执行结果。"""
        rejections = (
            CapabilityUnavailable(reason="当前未接入所需能力"),
            InputInsufficient(reason="缺少必需的目标视图"),
        )
        for rejection in rejections:
            with self.subTest(rejection=rejection):
                with self.assertRaises(TypeError):
                    validate_attempt_fact(cast(AttemptObservation, rejection), attempt=self.attempt)
                with self.assertRaises(TypeError):
                    reconcile_observation(None, cast(AttemptObservation, rejection))
        with self.assertRaises(ExecutionContractError):
            CapabilityUnavailable(reason=" ")
        with self.assertRaises(ExecutionContractError):
            InputInsufficient(reason="\ud800")
