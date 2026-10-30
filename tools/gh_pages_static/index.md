---
layout: default
title: Droso project notes
---

# Droso

<p class="eyebrow">Project notes</p>

Working notes for a hybrid agent: a sparse associative memory bound to a small
language model, with a connectome layer for housekeeping. The pages below are
dated logs and design records. Every number traces to a benchmark report in
the repository.

<ul class="doc-list">
  <li>
    <a href="speech_log.html">Speech log</a>
    <span class="doc-sub">Dated log of speech fixes and benchmark reruns, including the role_chain cold recall fix.</span>
  </li>
  <li>
    <a href="cross_session_design.html">Cross session design</a>
    <span class="doc-sub">Design for cross-session recall: graded freshness restricted to who said it, and the guard set that verifies it.</span>
  </li>
  <li>
    <li>
    <a href="STATE.html">State at handover</a>
    <span class="doc-sub">The current floor and what it means, every landed mechanism marked general or narrow, every reverted axis with its cause, the harness commands, and what is not done.</span>
  </li>
  <li>
    <a href="benchmark_findings.html">Benchmark findings</a>
    <span class="doc-sub">Why the warm scripts fail: measured drops, retrieval traces, and the diagnosis.</span>
  </li>
  <li>
    <a href="debt_log.html">Debt log</a>
    <span class="doc-sub">Fixes and tests that exist but are not fully verified, with status stated per item.</span>
  </li>
  <li>
    <a href="mine_criteria.html">Mining criteria</a>
    <span class="doc-sub">Frozen criteria for primitive mining, written before the first run.</span>
  </li>
</ul>