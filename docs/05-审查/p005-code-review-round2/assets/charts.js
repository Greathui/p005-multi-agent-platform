(function() {
  var style = getComputedStyle(document.documentElement);
  var accent = style.getPropertyValue('--accent').trim();
  var accent2 = style.getPropertyValue('--accent2').trim();
  var ink = style.getPropertyValue('--ink').trim();
  var muted = style.getPropertyValue('--muted').trim();
  var rule = style.getPropertyValue('--rule').trim();
  var bg2 = style.getPropertyValue('--bg2').trim();

  // --- Chart 1: 修复率对比 ---
  var chart1 = echarts.init(document.getElementById('chart-fix-rate'), null, { renderer: 'svg' });
  chart1.setOption({
    tooltip: { trigger: 'axis', appendToBody: true },
    legend: { data: ['第一轮', '第二轮'], bottom: 0, textStyle: { color: muted } },
    grid: { left: '3%', right: '4%', bottom: '15%', containLabel: true },
    xAxis: { type: 'category', data: ['后端', '前端', '元团队/蓝图', '安全机制', '数据一致性'], axisLabel: { color: ink }, axisLine: { lineStyle: { color: rule } } },
    yAxis: { type: 'value', max: 100, axisLabel: { color: muted, formatter: '{value}%' }, axisLine: { lineStyle: { color: rule } }, splitLine: { lineStyle: { color: rule } } },
    series: [
      { name: '第一轮', type: 'bar', data: [60, 65, 55, 67, 60], itemStyle: { color: '#94a3b8', borderRadius: [4,4,0,0] }, barGap: '10%' },
      { name: '第二轮', type: 'bar', data: [85, 87, 70, 90, 88], itemStyle: { color: accent, borderRadius: [4,4,0,0] } }
    ]
  });

  // --- Chart 2: 修复状态分布 ---
  var chart2 = echarts.init(document.getElementById('chart-status'), null, { renderer: 'svg' });
  chart2.setOption({
    tooltip: { trigger: 'item', appendToBody: true },
    legend: { bottom: 0, textStyle: { color: muted } },
    series: [{
      type: 'pie',
      radius: ['45%', '75%'],
      avoidLabelOverlap: false,
      itemStyle: { borderRadius: 8, borderColor: '#fff', borderWidth: 2 },
      label: { show: true, formatter: '{b}: {c}项', color: ink },
      emphasis: { label: { show: true, fontSize: 16, fontWeight: 'bold' } },
      data: [
        { value: 36, name: '已修复', itemStyle: { color: '#10b981' } },
        { value: 7, name: '部分修复', itemStyle: { color: '#f59e0b' } },
        { value: 13, name: '未修复', itemStyle: { color: '#ef4444' } }
      ]
    }]
  });

  // --- Chart 3: 各模块得分雷达 ---
  var chart3 = echarts.init(document.getElementById('chart-radar'), null, { renderer: 'svg' });
  chart3.setOption({
    tooltip: { trigger: 'axis', appendToBody: true },
    legend: { data: ['第一轮(66分)', '第二轮(82分)'], bottom: 0, textStyle: { color: muted } },
    radar: {
      indicator: [
        { name: '安全性', max: 100 },
        { name: '功能完整性', max: 100 },
        { name: '代码组织', max: 100 },
        { name: '错误处理', max: 100 },
        { name: '性能优化', max: 100 },
        { name: '可维护性', max: 100 }
      ],
      axisName: { color: ink },
      splitArea: { areaStyle: { color: [bg2, 'transparent'] } },
      axisLine: { lineStyle: { color: rule } },
      splitLine: { lineStyle: { color: rule } }
    },
    series: [{
      type: 'radar',
      data: [
        { value: [67, 87, 50, 65, 60, 45], name: '第一轮(66分)', areaStyle: { color: '#94a3b8' + '30' }, lineStyle: { color: '#94a3b8', width: 2 }, itemStyle: { color: '#94a3b8' }, symbol: 'none' },
        { value: [88, 90, 62, 78, 82, 58], name: '第二轮(82分)', areaStyle: { color: accent + '30' }, lineStyle: { color: accent, width: 2 }, itemStyle: { color: accent } }
      ]
    }]
  });

  // --- Chart 4: 问题严重度变化 ---
  var chart4 = echarts.init(document.getElementById('chart-compare'), null, { renderer: 'svg' });
  chart4.setOption({
    tooltip: { trigger: 'axis', appendToBody: true },
    legend: { data: ['第一轮(66项)', '第二轮(20项)'], bottom: 0, textStyle: { color: muted } },
    grid: { left: '3%', right: '4%', bottom: '15%', containLabel: true },
    xAxis: { type: 'category', data: ['严重(P0)', '中级(P1)', '轻微(P2)'], axisLabel: { color: ink }, axisLine: { lineStyle: { color: rule } } },
    yAxis: { type: 'value', axisLabel: { color: muted }, axisLine: { lineStyle: { color: rule } }, splitLine: { lineStyle: { color: rule } } },
    series: [
      { name: '第一轮(66项)', type: 'bar', data: [11, 25, 30], itemStyle: { color: '#94a3b8', borderRadius: [4,4,0,0] }, barGap: '10%' },
      { name: '第二轮(20项)', type: 'bar', data: [2, 8, 10], itemStyle: { color: accent, borderRadius: [4,4,0,0] } }
    ]
  });

  window.addEventListener('resize', function() {
    chart1.resize(); chart2.resize(); chart3.resize(); chart4.resize();
  });
})();