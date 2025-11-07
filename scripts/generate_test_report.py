#!/usr/bin/env python3
"""
Generate rich markdown reports from test results with graphs
"""
import os
import sys
import json
import base64
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Optional

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

try:
    import matplotlib
    matplotlib.use('Agg')  # Non-interactive backend
    import matplotlib.pyplot as plt
    import numpy as np
    HAS_MATPLOTLIB = True
except ImportError:
    HAS_MATPLOTLIB = False
    print("Warning: matplotlib not available, graphs will be skipped")

from scripts.compare_test_runs import load_test_results_from_db, compare_configurations, find_best_configuration


def generate_graphs(results: List[Dict], output_dir: Path) -> Dict[str, str]:
    """Generate graphs and return paths/embeddings"""
    graphs = {}
    
    if not HAS_MATPLOTLIB:
        return graphs
    
    # 1. Pass rate by configuration (bar chart)
    config_metrics = compare_configurations(results)
    if config_metrics:
        configs = []
        pass_rates = []
        for config_key, metrics in sorted(config_metrics.items(), key=lambda x: x[1]["pass_rate"], reverse=True):
            config = metrics["configuration"]
            config_str = f"{config.get('rag_strategy', 'unknown')}\nBM25:{config.get('hybrid_bm25_weight', 0.5):.1f}"
            configs.append(config_str)
            pass_rates.append(metrics["pass_rate"] * 100)
        
        plt.figure(figsize=(10, 6))
        plt.bar(range(len(configs)), pass_rates, color='steelblue')
        plt.xlabel('Configuration')
        plt.ylabel('Pass Rate (%)')
        plt.title('Pass Rate by Configuration')
        plt.xticks(range(len(configs)), configs, rotation=45, ha='right')
        plt.ylim(0, 100)
        plt.grid(axis='y', alpha=0.3)
        plt.tight_layout()
        
        graph_path = output_dir / "pass_rate_by_config.png"
        plt.savefig(graph_path, dpi=150, bbox_inches='tight')
        plt.close()
        graphs["pass_rate"] = str(graph_path.relative_to(Path.cwd()))
    
    # 2. Chunk quality distribution (histogram)
    chunk_qualities = [r.get("chunk_quality", 0) * 100 for r in results if r.get("chunk_quality") is not None]
    if chunk_qualities:
        plt.figure(figsize=(10, 6))
        plt.hist(chunk_qualities, bins=20, color='green', alpha=0.7, edgecolor='black')
        plt.xlabel('Chunk Quality (%)')
        plt.ylabel('Frequency')
        plt.title('Chunk Quality Distribution')
        plt.grid(axis='y', alpha=0.3)
        plt.tight_layout()
        
        graph_path = output_dir / "chunk_quality_distribution.png"
        plt.savefig(graph_path, dpi=150, bbox_inches='tight')
        plt.close()
        graphs["chunk_quality"] = str(graph_path.relative_to(Path.cwd()))
    
    # 3. Response time comparison (box plot)
    config_metrics = compare_configurations(results)
    if config_metrics:
        response_times_by_config = []
        config_labels = []
        for config_key, metrics in config_metrics.items():
            config_results = [r for r in results if json.dumps(r.get("configuration", {}), sort_keys=True) == config_key]
            times = [r.get("response_time_ms", 0) for r in config_results]
            if times:
                response_times_by_config.append(times)
                config = metrics["configuration"]
                config_labels.append(f"{config.get('rag_strategy', 'unknown')}")
        
        if response_times_by_config:
            plt.figure(figsize=(10, 6))
            plt.boxplot(response_times_by_config, labels=config_labels)
            plt.xlabel('Configuration')
            plt.ylabel('Response Time (ms)')
            plt.title('Response Time Comparison by Configuration')
            plt.xticks(rotation=45, ha='right')
            plt.grid(axis='y', alpha=0.3)
            plt.tight_layout()
            
            graph_path = output_dir / "response_time_comparison.png"
            plt.savefig(graph_path, dpi=150, bbox_inches='tight')
            plt.close()
            graphs["response_time"] = str(graph_path.relative_to(Path.cwd()))
    
    # 4. Configuration performance heatmap
    if config_metrics:
        strategies = sorted(set(c["configuration"].get("rag_strategy", "unknown") for c in config_metrics.values()))
        bm25_weights = sorted(set(c["configuration"].get("hybrid_bm25_weight", 0.5) for c in config_metrics.values()))
        
        if strategies and bm25_weights:
            heatmap_data = []
            for strategy in strategies:
                row = []
                for bm25_weight in bm25_weights:
                    # Find matching config
                    score = 0
                    for config_key, metrics in config_metrics.items():
                        config = metrics["configuration"]
                        if (config.get("rag_strategy") == strategy and 
                            abs(config.get("hybrid_bm25_weight", 0.5) - bm25_weight) < 0.01):
                            score = metrics["pass_rate"] * 100
                            break
                    row.append(score)
                heatmap_data.append(row)
            
            if heatmap_data:
                plt.figure(figsize=(10, 6))
                plt.imshow(heatmap_data, aspect='auto', cmap='RdYlGn', vmin=0, vmax=100)
                plt.colorbar(label='Pass Rate (%)')
                plt.xlabel('BM25 Weight')
                plt.ylabel('Strategy')
                plt.xticks(range(len(bm25_weights)), [f"{w:.1f}" for w in bm25_weights])
                plt.yticks(range(len(strategies)), strategies)
                plt.title('Configuration Performance Heatmap')
                plt.tight_layout()
                
                graph_path = output_dir / "config_performance_heatmap.png"
                plt.savefig(graph_path, dpi=150, bbox_inches='tight')
                plt.close()
                graphs["heatmap"] = str(graph_path.relative_to(Path.cwd()))
    
    return graphs


def generate_markdown_report(
    results: List[Dict],
    output_file: Path,
    include_graphs: bool = True
) -> None:
    """Generate comprehensive markdown report"""
    config_metrics = compare_configurations(results)
    best_config = find_best_configuration(config_metrics)
    
    # Generate graphs
    graphs = {}
    if include_graphs:
        graph_dir = output_file.parent / "graphs"
        graph_dir.mkdir(exist_ok=True)
        graphs = generate_graphs(results, graph_dir)
    
    # Calculate overall metrics
    total = len(results)
    passed = sum(1 for r in results if r.get("accuracy_score", 0) >= 0.7)
    avg_accuracy = sum(r.get("accuracy_score", 0) or 0 for r in results) / total if total > 0 else 0
    avg_chunk_quality = sum(r.get("chunk_quality", 0) for r in results) / total if total > 0 else 0
    avg_response_time = sum(r.get("response_time_ms", 0) for r in results) / total if total > 0 else 0
    
    # Build report
    report = []
    report.append("# RAG Test Report")
    report.append(f"\n**Generated:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    report.append(f"**Total Test Runs:** {total}")
    report.append("")
    
    # Executive Summary
    report.append("## Executive Summary")
    report.append("")
    report.append(f"- **Pass Rate:** {passed}/{total} ({100*passed/total:.1f}%)")
    report.append(f"- **Average Accuracy:** {avg_accuracy:.1%}")
    report.append(f"- **Average Chunk Quality:** {avg_chunk_quality:.1%}")
    report.append(f"- **Average Response Time:** {avg_response_time:.0f}ms")
    if best_config:
        report.append(f"- **Best Configuration:** {best_config['configuration']}")
    report.append("")
    
    # Configuration Comparison
    report.append("## Configuration Comparison")
    report.append("")
    report.append("| Configuration | Pass Rate | Avg Accuracy | Chunk Quality | Response Time |")
    report.append("|--------------|-----------|--------------|---------------|---------------|")
    
    for config_key, metrics in sorted(config_metrics.items(), key=lambda x: x[1]["pass_rate"], reverse=True):
        config = metrics["configuration"]
        config_str = f"{config.get('rag_strategy', 'unknown')} (BM25:{config.get('hybrid_bm25_weight', 0.5):.1f})"
        report.append(
            f"| {config_str} | {metrics['pass_rate']:.1%} | {metrics['avg_accuracy']:.1%} | "
            f"{metrics['avg_chunk_quality']:.1%} | {metrics['avg_response_time']:.0f}ms |"
        )
    report.append("")
    
    # Graphs
    if graphs:
        report.append("## Performance Visualizations")
        report.append("")
        if "pass_rate" in graphs:
            report.append(f"### Pass Rate by Configuration")
            report.append(f"![Pass Rate]({graphs['pass_rate']})")
            report.append("")
        if "chunk_quality" in graphs:
            report.append(f"### Chunk Quality Distribution")
            report.append(f"![Chunk Quality]({graphs['chunk_quality']})")
            report.append("")
        if "response_time" in graphs:
            report.append(f"### Response Time Comparison")
            report.append(f"![Response Time]({graphs['response_time']})")
            report.append("")
        if "heatmap" in graphs:
            report.append(f"### Configuration Performance Heatmap")
            report.append(f"![Heatmap]({graphs['heatmap']})")
            report.append("")
    
    # Best/Worst Questions
    report.append("## Question Performance")
    report.append("")
    
    # Group by question
    question_performance = {}
    for result in results:
        qid = result.get("question_id")
        if qid not in question_performance:
            question_performance[qid] = {
                "question_text": result.get("question_text", "Unknown"),
                "results": [],
            }
        question_performance[qid]["results"].append(result)
    
    # Calculate per-question metrics
    question_metrics = []
    for qid, data in question_performance.items():
        q_results = data["results"]
        total = len(q_results)
        passed = sum(1 for r in q_results if r.get("accuracy_score", 0) >= 0.7)
        avg_accuracy = sum(r.get("accuracy_score", 0) or 0 for r in q_results) / total if total > 0 else 0
        question_metrics.append({
            "question_id": qid,
            "question_text": data["question_text"],
            "total": total,
            "passed": passed,
            "pass_rate": passed / total if total > 0 else 0,
            "avg_accuracy": avg_accuracy,
        })
    
    question_metrics.sort(key=lambda x: x["pass_rate"])
    
    # Worst performing
    report.append("### Worst Performing Questions")
    report.append("")
    report.append("| Question | Pass Rate | Avg Accuracy |")
    report.append("|----------|-----------|--------------|")
    for qm in question_metrics[:10]:
        status = "✅" if qm["pass_rate"] >= 0.7 else "❌"
        report.append(f"| {status} {qm['question_text'][:60]}... | {qm['pass_rate']:.1%} | {qm['avg_accuracy']:.1%} |")
    report.append("")
    
    # Best performing
    report.append("### Best Performing Questions")
    report.append("")
    report.append("| Question | Pass Rate | Avg Accuracy |")
    report.append("|----------|-----------|--------------|")
    for qm in reversed(question_metrics[-10:]):
        status = "✅" if qm["pass_rate"] >= 0.7 else "❌"
        report.append(f"| {status} {qm['question_text'][:60]}... | {qm['pass_rate']:.1%} | {qm['avg_accuracy']:.1%} |")
    report.append("")
    
    # Detailed Results
    report.append("## Detailed Results")
    report.append("")
    report.append("| Question | Expected | Actual | Accuracy | Chunk Quality | Status |")
    report.append("|----------|----------|--------|----------|---------------|--------|")
    
    for result in results[:50]:  # Limit to first 50 for readability
        expected = result.get("expected_answer", "N/A")[:30] if result.get("expected_answer") else "N/A"
        actual = result.get("actual_answer", "N/A")[:30] if result.get("actual_answer") else "N/A"
        accuracy = result.get("accuracy_score", 0) or 0
        chunk_quality = result.get("chunk_quality", 0)
        passed = accuracy >= 0.7
        status = "✅" if passed else "❌"
        
        report.append(
            f"| {result.get('question_text', 'Unknown')[:40]}... | {expected} | {actual} | "
            f"{accuracy:.1%} | {chunk_quality:.1%} | {status} |"
        )
    report.append("")
    
    # Write report
    output_file.parent.mkdir(parents=True, exist_ok=True)
    with open(output_file, "w") as f:
        f.write("\n".join(report))
    
    print(f"Report generated: {output_file}")


def main():
    import argparse
    
    parser = argparse.ArgumentParser(description="Generate markdown test report")
    parser.add_argument("--question-ids", nargs="+", help="Specific question IDs")
    parser.add_argument("--limit", type=int, help="Limit number of test runs")
    parser.add_argument("--output", type=str, help="Output markdown file")
    parser.add_argument("--no-graphs", action="store_true", help="Skip graph generation")
    
    args = parser.parse_args()
    
    # Load results
    results = load_test_results_from_db(
        question_ids=args.question_ids,
        limit=args.limit
    )
    
    # Generate report
    if args.output:
        output_file = Path(args.output)
    else:
        output_file = Path("reports") / f"rag_test_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.md"
    
    generate_markdown_report(results, output_file, include_graphs=not args.no_graphs)


if __name__ == "__main__":
    main()


