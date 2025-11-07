#!/usr/bin/env python3
"""
Analyze context window performance test results and generate plots
"""

import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns
from pathlib import Path
import json

# Set style
sns.set_style("whitegrid")
plt.rcParams['figure.figsize'] = (12, 8)

RESULTS_DIR = Path(__file__).parent / "results"
OUTPUT_DIR = Path(__file__).parent / "results"

def load_latest_results():
    """Load the most recent results file"""
    csv_files = sorted(RESULTS_DIR.glob("results_*.csv"))
    if not csv_files:
        raise FileNotFoundError("No results files found")
    
    latest = csv_files[-1]
    print(f"Loading: {latest.name}")
    
    df = pd.read_csv(latest)
    return df, latest.stem

def create_plots(df):
    """Create all analysis plots"""
    OUTPUT_DIR.mkdir(exist_ok=True)
    
    # 1. Response Time vs Context Window Size (by model)
    fig, axes = plt.subplots(1, 2, figsize=(16, 6))
    
    for idx, model in enumerate(['llama3.2:1b', 'llama3.2:3b']):
        model_data = df[df['model'] == model]
        for context_size in sorted(model_data['context_size'].unique()):
            ctx_data = model_data[model_data['context_size'] == context_size]
            axes[idx].plot(ctx_data['corpus_size'], ctx_data['avg_duration'], 
                         marker='o', label=f'Context {context_size}', linewidth=2)
        
        axes[idx].set_xlabel('Corpus Size (characters)', fontsize=12)
        axes[idx].set_ylabel('Average Response Time (seconds)', fontsize=12)
        axes[idx].set_title(f'Response Time vs Corpus Size - {model}', fontsize=14, fontweight='bold')
        axes[idx].legend()
        axes[idx].grid(True, alpha=0.3)
    
    plt.tight_layout()
    plt.savefig(OUTPUT_DIR / 'response_time_vs_corpus.png', dpi=300, bbox_inches='tight')
    print(f"✅ Saved: response_time_vs_corpus.png")
    plt.close()
    
    # 2. Response Time vs Context Window Size
    fig, ax = plt.subplots(figsize=(12, 6))
    
    for model in ['llama3.2:1b', 'llama3.2:3b']:
        model_data = df[df['model'] == model]
        avg_by_context = model_data.groupby('context_size')['avg_duration'].mean()
        ax.plot(avg_by_context.index, avg_by_context.values, 
               marker='o', label=model, linewidth=3, markersize=10)
    
    ax.set_xlabel('Context Window Size', fontsize=12)
    ax.set_ylabel('Average Response Time (seconds)', fontsize=12)
    ax.set_title('Response Time vs Context Window Size (Average Across All Corpus Sizes)', 
                fontsize=14, fontweight='bold')
    ax.legend(fontsize=11)
    ax.grid(True, alpha=0.3)
    plt.tight_layout()
    plt.savefig(OUTPUT_DIR / 'response_time_vs_context.png', dpi=300, bbox_inches='tight')
    print(f"✅ Saved: response_time_vs_context.png")
    plt.close()
    
    # 3. Confidence vs Context Window Size
    fig, ax = plt.subplots(figsize=(12, 6))
    
    for model in ['llama3.2:1b', 'llama3.2:3b']:
        model_data = df[df['model'] == model]
        avg_by_context = model_data.groupby('context_size')['avg_confidence'].mean()
        ax.plot(avg_by_context.index, avg_by_context.values, 
               marker='s', label=model, linewidth=3, markersize=10)
    
    ax.set_xlabel('Context Window Size', fontsize=12)
    ax.set_ylabel('Average Confidence Score', fontsize=12)
    ax.set_title('Confidence vs Context Window Size (Average Across All Corpus Sizes)', 
                fontsize=14, fontweight='bold')
    ax.legend(fontsize=11)
    ax.grid(True, alpha=0.3)
    plt.tight_layout()
    plt.savefig(OUTPUT_DIR / 'confidence_vs_context.png', dpi=300, bbox_inches='tight')
    print(f"✅ Saved: confidence_vs_context.png")
    plt.close()
    
    # 4. Heatmap: Response Time by Context Size and Corpus Size
    fig, axes = plt.subplots(1, 2, figsize=(18, 6))
    
    for idx, model in enumerate(['llama3.2:1b', 'llama3.2:3b']):
        model_data = df[df['model'] == model]
        pivot = model_data.pivot_table(
            values='avg_duration',
            index='corpus_size',
            columns='context_size',
            aggfunc='mean'
        )
        
        sns.heatmap(pivot, annot=True, fmt='.2f', cmap='YlOrRd', 
                   ax=axes[idx], cbar_kws={'label': 'Response Time (s)'})
        axes[idx].set_title(f'Response Time Heatmap - {model}', fontsize=14, fontweight='bold')
        axes[idx].set_xlabel('Context Window Size', fontsize=12)
        axes[idx].set_ylabel('Corpus Size (characters)', fontsize=12)
    
    plt.tight_layout()
    plt.savefig(OUTPUT_DIR / 'response_time_heatmap.png', dpi=300, bbox_inches='tight')
    print(f"✅ Saved: response_time_heatmap.png")
    plt.close()
    
    # 5. Model Comparison: Side by side
    fig, axes = plt.subplots(2, 2, figsize=(16, 12))
    
    # Time comparison
    for model in ['llama3.2:1b', 'llama3.2:3b']:
        model_data = df[df['model'] == model]
        avg_time = model_data.groupby('context_size')['avg_duration'].mean()
        axes[0, 0].bar([f"{m}\n{ctx}" for ctx, m in zip(avg_time.index, [model.split(':')[1]] * len(avg_time))], 
                      avg_time.values, label=model, alpha=0.7)
    axes[0, 0].set_ylabel('Avg Response Time (s)', fontsize=11)
    axes[0, 0].set_title('Average Response Time by Model and Context Size', fontsize=12, fontweight='bold')
    axes[0, 0].legend()
    axes[0, 0].tick_params(axis='x', rotation=45)
    
    # Confidence comparison
    for model in ['llama3.2:1b', 'llama3.2:3b']:
        model_data = df[df['model'] == model]
        avg_conf = model_data.groupby('context_size')['avg_confidence'].mean()
        axes[0, 1].bar([f"{m}\n{ctx}" for ctx, m in zip(avg_conf.index, [model.split(':')[1]] * len(avg_conf))], 
                      avg_conf.values, label=model, alpha=0.7)
    axes[0, 1].set_ylabel('Avg Confidence', fontsize=11)
    axes[0, 1].set_title('Average Confidence by Model and Context Size', fontsize=12, fontweight='bold')
    axes[0, 1].legend()
    axes[0, 1].tick_params(axis='x', rotation=45)
    
    # Corpus size effect on time
    for model in ['llama3.2:1b', 'llama3.2:3b']:
        model_data = df[df['model'] == model]
        axes[1, 0].scatter(model_data['corpus_size'], model_data['avg_duration'], 
                          label=model, alpha=0.6, s=50)
    axes[1, 0].set_xlabel('Corpus Size (characters)', fontsize=11)
    axes[1, 0].set_ylabel('Response Time (s)', fontsize=11)
    axes[1, 0].set_title('Response Time vs Corpus Size', fontsize=12, fontweight='bold')
    axes[1, 0].legend()
    axes[1, 0].grid(True, alpha=0.3)
    
    # Corpus size effect on confidence
    for model in ['llama3.2:1b', 'llama3.2:3b']:
        model_data = df[df['model'] == model]
        axes[1, 1].scatter(model_data['corpus_size'], model_data['avg_confidence'], 
                          label=model, alpha=0.6, s=50)
    axes[1, 1].set_xlabel('Corpus Size (characters)', fontsize=11)
    axes[1, 1].set_ylabel('Confidence', fontsize=11)
    axes[1, 1].set_title('Confidence vs Corpus Size', fontsize=12, fontweight='bold')
    axes[1, 1].legend()
    axes[1, 1].grid(True, alpha=0.3)
    
    plt.tight_layout()
    plt.savefig(OUTPUT_DIR / 'model_comparison.png', dpi=300, bbox_inches='tight')
    print(f"✅ Saved: model_comparison.png")
    plt.close()

def generate_report(df, filename):
    """Generate text report with statistics"""
    report = []
    report.append("="*70)
    report.append("Context Window Performance Analysis Report")
    report.append("="*70)
    report.append("")
    
    # Overall statistics
    report.append("Overall Statistics:")
    report.append("-"*70)
    report.append(f"Total tests: {len(df)}")
    report.append(f"Models tested: {df['model'].nunique()}")
    report.append(f"Context sizes tested: {sorted(df['context_size'].unique())}")
    report.append(f"Average response time: {df['avg_duration'].mean():.2f}s")
    report.append(f"Average confidence: {df['avg_confidence'].mean():.2f}")
    report.append("")
    
    # By model
    report.append("Performance by Model:")
    report.append("-"*70)
    for model in ['llama3.2:1b', 'llama3.2:3b']:
        model_data = df[df['model'] == model]
        report.append(f"\n{model}:")
        report.append(f"  Avg response time: {model_data['avg_duration'].mean():.2f}s")
        report.append(f"  Min response time: {model_data['avg_duration'].min():.2f}s")
        report.append(f"  Max response time: {model_data['avg_duration'].max():.2f}s")
        report.append(f"  Avg confidence: {model_data['avg_confidence'].mean():.2f}")
    report.append("")
    
    # By context size
    report.append("Performance by Context Window Size:")
    report.append("-"*70)
    for ctx_size in sorted(df['context_size'].unique()):
        ctx_data = df[df['context_size'] == ctx_size]
        report.append(f"\nContext {ctx_size}:")
        report.append(f"  Avg response time: {ctx_data['avg_duration'].mean():.2f}s")
        report.append(f"  Avg confidence: {ctx_data['avg_confidence'].mean():.2f}")
    report.append("")
    
    # Key findings
    report.append("Key Findings:")
    report.append("-"*70)
    
    # Fastest configuration
    fastest = df.loc[df['avg_duration'].idxmin()]
    report.append(f"\nFastest configuration:")
    report.append(f"  Model: {fastest['model']}")
    report.append(f"  Context: {fastest['context_size']}")
    report.append(f"  Corpus: {fastest['corpus_size']} chars")
    report.append(f"  Time: {fastest['avg_duration']:.2f}s")
    
    # Highest confidence
    highest_conf = df.loc[df['avg_confidence'].idxmax()]
    report.append(f"\nHighest confidence:")
    report.append(f"  Model: {highest_conf['model']}")
    report.append(f"  Context: {highest_conf['context_size']}")
    report.append(f"  Corpus: {highest_conf['corpus_size']} chars")
    report.append(f"  Confidence: {highest_conf['avg_confidence']:.2f}")
    
    # Model comparison
    report.append(f"\nModel Comparison:")
    for model in ['llama3.2:1b', 'llama3.2:3b']:
        model_data = df[df['model'] == model]
        report.append(f"  {model}: {model_data['avg_duration'].mean():.2f}s avg, "
                     f"{model_data['avg_confidence'].mean():.2f} confidence")
    
    report.append("")
    report.append("="*70)
    
    report_text = "\n".join(report)
    
    with open(OUTPUT_DIR / f"{filename}_report.txt", 'w') as f:
        f.write(report_text)
    
    print(f"✅ Saved: {filename}_report.txt")
    print("\n" + report_text)

def main():
    """Main analysis"""
    print("="*70)
    print("Context Window Performance Analysis")
    print("="*70)
    print()
    
    df, filename = load_latest_results()
    print(f"Loaded {len(df)} test results")
    print()
    
    create_plots(df)
    print()
    generate_report(df, filename)
    
    print("\n" + "="*70)
    print("Analysis complete!")
    print(f"Results saved to: {OUTPUT_DIR}")
    print("="*70)

if __name__ == "__main__":
    main()

