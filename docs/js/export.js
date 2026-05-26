// export.js — descarga Excel con resultados
const Export = (() => {
  function downloadExcel() {
    const d = Data.get();
    if (!d) { App.toast('Sin datos cargados', 'error'); return; }

    const wb = XLSX.utils.book_new();

    // Hoja 1: Score Final
    const clients = d.top_clients || [];
    const ws1 = XLSX.utils.json_to_sheet(clients.map(c => ({
      'Customer ID':         c.customer_id,
      'País':                c.country_code,
      'Score Final':         c.score_final,
      'Nivel Riesgo Final':  c.nivel_riesgo_final,
      'Score Cliente':       c.score_cliente,
      'Score Jurisdicción':  c.score_jurisdiccion,
      'Score Producto':      c.score_producto,
      'Score Canal':         c.score_canal,
      'Principales Drivers': c.principales_drivers,
    })));
    XLSX.utils.book_append_sheet(wb, ws1, '03_score_final');

    // Hoja 2: Resumen por segmento
    const segs = d.segment_summary || [];
    const ws2 = XLSX.utils.json_to_sheet(segs.map(s => ({
      'Nivel Riesgo':    s.nivel,
      'Total Clientes':  s.total,
      '% del Total':     (s.pct * 100).toFixed(1) + '%',
      'Score Promedio':  s.score_avg,
    })));
    XLSX.utils.book_append_sheet(wb, ws2, '04_resumen_segmentos');

    // Hoja 3: Riesgo por país
    const countries = d.country_risk_summary || [];
    const ws3 = XLSX.utils.json_to_sheet(countries.map(c => ({
      'Código País':    c.country_code,
      'País':           c.country_name,
      'Total Clientes': c.total_clients,
      'Score Promedio': c.avg_score,
    })));
    XLSX.utils.book_append_sheet(wb, ws3, 'paises');

    // Metadatos
    const ws4 = XLSX.utils.json_to_sheet([{
      'Fecha corrida':     d.run_date,
      'Versión modelo':    d.model_version,
      'Total evaluados':   d.summary?.total_clients,
      'Peso Clientes':     d.summary?.weights?.clientes,
      'Peso Jurisdicciones': d.summary?.weights?.jurisdicciones,
      'Peso Productos':    d.summary?.weights?.productos,
      'Peso Canales':      d.summary?.weights?.canales,
    }]);
    XLSX.utils.book_append_sheet(wb, ws4, 'metadatos');

    XLSX.writeFile(wb, `segmentacion_laft_${d.run_date}.xlsx`);
    App.toast('Excel descargado correctamente', 'success');
  }

  function updatePreview() {
    const d = Data.get();
    if (!d) return;
    const el = document.getElementById('export-preview');
    if (el) {
      el.textContent = `${d.top_clients?.length || 0} clientes en el archivo | Corrida: ${d.run_date} | Versión: ${d.model_version}`;
    }
  }

  return { downloadExcel, updatePreview };
})();
