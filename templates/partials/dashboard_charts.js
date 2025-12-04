
(async function () {
  // Busca dados agregados por mês
  let apiData;
  try {
    const res = await fetch("{{ url_for('api_recharges_monthly') }}");
    apiData = await res.json();
  } catch (err) {
    console.error(LoadMonthlyDataErrorMessage, err);
    document.querySelectorAll('.chart-container').forEach(el => {
      el.innerHTML = `<div class="text-muted">${LoadDataUnavailableMessage}</div>`;
    });
    return;
  }

  // Se não houver dados
  if (!apiData || !apiData.labels || apiData.labels.length === 0) {
    document.querySelectorAll('.chart-container').forEach(el => {
      el.innerHTML = `<div class="text-muted">${NoDataToDisplayMessage}</div>`;
    });
    return;
  }

  // Converte "YYYY-MM" -> "MM/YYYY"
  const labels = apiData.labels.map(m => `${m.slice(5, 7)}/${m.slice(0, 4)}`);

  // Helpers de formatação
  const fmtBRL = v => CurrencySymbolBRL + ' ' + Number(v ?? 0).toLocaleString(LocaleCodePtBR, {minimumFractionDigits: 2, maximumFractionDigits: 2});
  const fmtNum = v => Number(v ?? 0).toLocaleString(LocaleCodePtBR, {maximumFractionDigits: 2});

  // ============ Gráfico 1: Custos por Mês ============ //
  new Chart(document.getElementById('chartCustos'), {
    type: 'bar',
    data: {
      labels,
      datasets: [
        {
          label: LabelTotalCostBRL,
          data: apiData.custos.total,
          backgroundColor: 'rgba(13,110,253,0.6)',
          borderColor: 'rgba(13,110,253,1)',
          borderWidth: 1,
          yAxisID: 'y'
        },
        {
          label: LabelPaidRechargesBRL,
          data: apiData.custos.pagas,
          backgroundColor: 'rgba(25,135,84,0.6)',
          borderColor: 'rgba(25,135,84,1)',
          borderWidth: 1,
          yAxisID: 'y'
        },
        {
          type: 'line',
          label: LabelPercentPaidOverTotal,
          data: apiData.custos.percentual,
          borderColor: 'rgba(255,193,7,1)',
          backgroundColor: 'rgba(255,193,7,0.2)',
          tension: 0.25,
          pointRadius: 3,
          yAxisID: 'yPerc'
        }
      ]
    },
    options: {
      responsive: true,
      interaction: { mode: 'index', intersect: false },
      scales: {
        y: {
          position: 'left',
          title: { display: true, text: CurrencySymbolBRL },
          ticks: { callback: value => fmtBRL(value) },
          beginAtZero: true
        },
        yPerc: {
          position: 'right',
          title: { display: true, text: '%' },
          ticks: { callback: value => value + '%' },
          beginAtZero: true,
          suggestedMax: 100,
          grid: { drawOnChartArea: false }
        }
      },
      plugins: {
        tooltip: {
          callbacks: {
            label: ctx => {
              const dsLabel = ctx.dataset.label || '';
              const v = ctx.raw;
              return ctx.dataset.yAxisID === 'yPerc'
                ? `${dsLabel}: ${v}%`
                : `${dsLabel}: ${fmtBRL(v)}`;
            }
          }
        },
        legend: { position: 'bottom' }
      }
    }
  });


// ============ Gráfico 2: Consumo por Mês (kWh) Consumo / 100Km ============ //
new Chart(document.getElementById('chartConsumo'), {
  type: 'bar',
  data: {
    labels,
    datasets: [
      {
        label: LabelKWhInMonth,
        data: apiData.consumo,
        backgroundColor: 'rgba(255,193,7,0.6)',
        borderColor: 'rgba(255,193,7,1)',
        borderWidth: 1,
        yAxisID: 'y'
      },
      {
        type: 'line',
        label: LabelKWhPer100Km,
        data: apiData.consumo_por_100km,
        borderColor: 'rgba(13,110,253,1)',
        backgroundColor: 'rgba(13,110,253,0.2)',
        tension: 0.25,
        pointRadius: 3,
        yAxisID: 'y2'
      }
    ]
  },
  options: {
    responsive: true,
    interaction: { mode: 'index', intersect: false },
    scales: {
      y: {
        position: 'left',
        title: { display: true, text: 'kWh' },
        ticks: { callback: value => fmtNum(value) },
        beginAtZero: true
      },
      y2: {
        position: 'right',
        title: { display: true, text: LabelKWhPer100Km },
        ticks: { callback: value => fmtNum(value) },
        beginAtZero: true,
        grid: { drawOnChartArea: false }
      }
    },
    plugins: {
      tooltip: {
        callbacks: {
          label: ctx => {
            const dsLabel = ctx.dataset.label || '';
            const v = ctx.raw;
            const unidade = ctx.dataset.yAxisID === 'y' ? 'kWh' : LabelKWhPer100Km;
            return `${dsLabel}: ${fmtNum(v)} ${unidade}`;
          }
        }
      },
      legend: { position: 'bottom' }
    }
  }
});


  // ============ Gráfico 3: Km Rodados por Mês ============ //
  new Chart(document.getElementById('chartKm'), {
    type: 'bar',
    data: {
      labels,
      datasets: [{
        label: LabelKmInMonth,
        data: apiData.km,
        backgroundColor: 'rgba(33,37,41,0.6)',
        borderColor: 'rgba(33,37,41,1)',
        borderWidth: 1
      }]
    },
    options: {
      responsive: true,
      scales: {
        y: {
          title: { display: true, text: LabelKm },
          ticks: { callback: value => fmtNum(value) },
          beginAtZero: true
        }
      },
      plugins: {
        tooltip: { callbacks: { label: c => `${c.dataset.label}: ${fmtNum(c.raw)} ${LabelKm}` } },
        legend: { position: 'bottom' }
      }
    }
  });

  // ============ Gráfico 4: Valores Economizados por Mês ============ //
  new Chart(document.getElementById('chartEconomia'), {
    type: 'bar',
    data: {
      labels,
      datasets: [
        {
          label: LabelTotalSavingsBRL,
          data: apiData.economia.total,
          backgroundColor: 'rgba(253,126,20,0.6)',
          borderColor: 'rgba(253,126,20,1)',
          borderWidth: 1
        },
        {
          label: LabelPaidSavingsBRL,
          data: apiData.economia.pagas,
          backgroundColor: 'rgba(108,117,125,0.6)',
          borderColor: 'rgba(108,117,125,1)',
          borderWidth: 1
        }
      ]
    },
    options: {
      responsive: true,
      scales: {
        y: {
          title: { display: true, text: CurrencySymbolBRL },
          ticks: { callback: value => fmtBRL(value) },
          beginAtZero: true
        }
      },
      plugins: {
        tooltip: { callbacks: { label: c => `${c.dataset.label}: ${fmtBRL(c.raw)}` } },
        legend: { position: 'bottom' }
      }
    }
  });
})();
