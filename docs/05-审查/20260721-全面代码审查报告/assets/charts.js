(function() {
  var style = getComputedStyle(document.documentElement);
  var accent = style.getPropertyValue('--accent').trim();
  var accent2 = style.getPropertyValue('--accent2').trim();
  var ink = style.getPropertyValue('--ink').trim();
  var muted = style.getPropertyValue('--muted').trim();
  var rule = style.getPropertyValue('--rule').trim();
  var bg2 = style.getPropertyValue('--bg2').trim();

  // --- Chart 1: 问题严重度分布 ---
  var chart1 = echarts.init(document.getElementById('chart-severity'), null, { renderer: 'svg' });
  chart1.setOption({
    tooltip: { trigger: 'item', appendToBody: true },
    legend: { bottom: 0, textStyle: { color: muted } },
    series: [{
      type: 'pie',
      radius: ['40%', '70%'],
      avoidLabelOverlap: false,
      itemStyle: { borderRadius: 8, borderColor: '#fff', borderWidth: 2 },
      label: { show: true, formatter: '{b}: {c}个', color: ink },
      data: [
        { value: 11, name: '严重(P0)', itemStyle: { color: '#ef4444' } },
        { value: 25, name: '中级(P1)', itemStyle: { color: '#f59e0b' } },
        { value: 30, name: '轻微(P2)', itemStyle: { color: '#3b82f6' } }
      ]
    }]
  });

  // --- Chart 2: 各模块问题分布 ---
  var chart2 = echarts.init(document.getElementById('chart-modules'), null, { renderer: 'svg' });
  chart2.setOption({
    tooltip: { trigger: 'axis', appendToBody: true, axisPointer: { type: 'shadow' } },
    grid: { left: '3%', right: '4%', bottom: '3%', containLabel: true },
    xAxis: { type: 'value', axisLabel: { color: muted }, axisLine: { lineStyle: { color: rule } } },
    yAxis: {
      type: 'category',
      data: ['元团队/蓝图', '数据/API一致性', '安全机制', '前端', '后端核心'],
      axisLabel: { color: ink },
      axisLine: { lineStyle: { color: rule } }
    },
    series: [{
      type: 'bar',
      data: [
        { value: 13, itemStyle: { color: accent2 } },
        { value: 11, itemStyle: { color: accent } },
        { value: 12, itemStyle: { color: '#ef4444' } },
        { value: 16, itemStyle: { color: '#8b5cf6' } },
        { value: 14, itemStyle: { color: '#06b6d4' } }
      ],
      barWidth: '60%',
      label: { show: true, position: 'right', color: ink }
    }]
  });

  // --- Chart 3: 安全防御层完整性 ---
  var chart3 = echarts.init(document.getElementById('chart-security'), null, { renderer: 'svg' });
  chart3.setOption({
    tooltip: { trigger: 'axis', appendToBody: true },
    radar: {
      indicator: [
        { name: '路径防护', max: 100 },
        { name: '权限隔离', max: 100 },
        { name: '防幻觉', max: 100 },
        { name: '工具过滤', max: 100 },
        { name: '密钥保护', max: 100 },
        { name: '并发安全', max: 100 }
      ],
      axisName: { color: ink },
      splitArea: { areaStyle: { color: [bg2, 'transparent'] } },
      axisLine: { lineStyle: { color: rule } },
      splitLine: { lineStyle: { color: rule } }
    },
    series: [{
      type: 'radar',
      data: [{
        value: [85, 70, 75, 90, 60, 20],
        name: '当前评分',
        areaStyle: { color: accent + '40' },
        lineStyle: { color: accent, width: 2 },
        itemStyle: { color: accent }
      }]
    }]
  });

  // --- Chart 4: 代码质量评分雷达 ---
  var chart4 = echarts.init(document.getElementById('chart-quality'), null, { renderer: 'svg' });
  chart4.setOption({
    tooltip: { trigger: 'axis', appendToBody: true },
    radar: {
      indicator: [
        { name: '功能完整性', max: 100 },
        { name: '代码组织', max: 100 },
        { name: '错误处理', max: 100 },
        { name: '性能优化', max: 100 },
        { name: '安全性', max: 100 },
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
        {
          value: [90, 50, 65, 60, 67, 45],
          name: '后端',
          areaStyle: { color: accent + '30' },
          lineStyle: { color: accent, width: 2 },
          itemStyle: { color: accent }
        },
        {
          value: [85, 60, 55, 55, 75, 55],
          name: '前端',
          areaStyle: { color: accent2 + '30' },
          lineStyle: { color: accent2, width: 2 },
          itemStyle: { color: accent2 }
        }
      ]
    }],
    legend: { bottom: 0, textStyle: { color: muted } }
  });

  window.addEventListener('resize', function() {
    chart1.resize();
    chart2.resize();
    chart3.resize();
    chart4.resize();
  });
})();
