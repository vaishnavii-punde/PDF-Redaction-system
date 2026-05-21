import matplotlib.pyplot as plt
import numpy as np

def generate_charts(cat_metrics, overall):
    plt.style.use('dark_background')
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(14, 6))
    fig.patch.set_facecolor('#1e1e1e')

    # Chart 1: Accuracy by Category
    cats = [c.upper() for c in cat_metrics.keys()]
    accs = [cat_metrics[c.lower()]['accuracy'] for c in cat_metrics.keys()]
    
    bars = ax1.bar(cats, accs, color='#10b981', alpha=0.8)
    ax1.set_title("Detection Accuracy by Category (%)", fontsize=12, pad=15)
    ax1.set_ylim(0, 110)
    
    # Add percentage labels on top of bars
    for bar in bars:
        height = bar.get_height()
        ax1.text(bar.get_x() + bar.get_width()/2., height + 2,
                f'{int(height)}%', ha='center', va='bottom', color='white')

    # Chart 2: Performance Donut/Pie
    labels = ['Precision', 'Recall', 'F1 Score']
    vals = [overall['precision'], overall['recall'], overall['f1']]
    
    # CRITICAL FIX: Only draw pie if there is data, else show "No Data"
    if sum(vals) > 0:
        ax2.pie(vals, labels=labels, autopct='%1.1f%%', startangle=140, 
                colors=['#5C7CB9', '#10b981', '#f59e0b'], 
                wedgeprops={'edgecolor': '#1e1e1e', 'linewidth': 2})
    else:
        ax2.text(0.5, 0.5, "No Matches Found\n(Scores are 0%)", 
                 ha='center', va='center', fontsize=14, color='#e15759')
    
    ax2.set_title("Overall System Health", fontsize=12, pad=15)

    plt.tight_layout()
    plt.savefig("evaluation_charts.png", facecolor='#1e1e1e')
    print("✅ Results saved to evaluation_charts.png")