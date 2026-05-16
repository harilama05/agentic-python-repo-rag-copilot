"""
📊 Evaluation — Streamlit page for running and viewing evaluation results.
"""

import streamlit as st
import json
from pathlib import Path

st.set_page_config(page_title="Evaluation", page_icon="📊", layout="wide")
st.title("📊 RAG Evaluation")

indexed = st.session_state.get("indexed_codebase")

if indexed is None:
    st.warning("⚠️ Please index a repository first (📁 Index Repository).")
    st.stop()

tab1, tab2 = st.tabs(["🧪 Run Evaluation", "📋 View Results"])

with tab1:
    st.subheader("Generate & Run Evaluation")

    num_cases = st.slider("Number of test cases", 5, 50, 20)

    if st.button("🎯 Generate Test Cases & Run", type="primary"):
        with st.spinner("Generating test cases..."):
            try:
                from src.evaluation.testset_builder import build_testset
                from src.evaluation.eval_runner import EvalRunner

                cases = build_testset(
                    metadata_store=indexed.metadata_store,
                    num_cases=num_cases,
                )

                st.write(f"Generated {len(cases)} test cases")

                runner = EvalRunner(indexed.agent)
                results = runner.run(cases)

                # Compute averages
                all_metrics = [r.metrics for r in results]
                avg_metrics = {}
                if all_metrics:
                    for key in all_metrics[0]:
                        values = [m.get(key, 0) for m in all_metrics]
                        avg_metrics[key] = round(sum(values) / len(values), 4)

                st.subheader("Average Metrics")
                cols = st.columns(len(avg_metrics))
                for col, (metric, value) in zip(cols, avg_metrics.items()):
                    with col:
                        st.metric(metric, f"{value:.2%}")

                st.subheader("Detailed Results")
                for i, result in enumerate(results):
                    with st.expander(f"Case {i+1}: {result.question[:60]}..."):
                        st.write(f"**Generated:** {result.generated_answer[:200]}...")
                        st.write(f"**Expected:** {result.expected_answer}")
                        st.json(result.metrics)

            except Exception as exc:
                st.error(f"Evaluation failed: {exc}")

with tab2:
    st.subheader("Load Results from File")
    eval_file = st.text_input("Results file path", "data/eval/eval_results.json")

    if Path(eval_file).exists():
        data = json.loads(Path(eval_file).read_text("utf-8"))
        st.json(data)
    else:
        st.info("No results file found. Run an evaluation first.")
