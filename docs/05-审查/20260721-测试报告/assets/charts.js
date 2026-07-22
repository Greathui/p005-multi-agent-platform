// P005 测试报告图表
(function() {
  var style = getComputedStyle(document.documentElement);
  var accent = style.getPropertyValue('--accent').trim();
  var accent2 = style.getPropertyValue('--accent2').trim();
  var ink = style.getPropertyValue('--ink').trim();
  var muted = style.getPropertyValue('--muted').trim();
  var rule = style.getPropertyValue('--rule').trim();
  var bg2 = style.getPropertyValue('--bg2').trim();
  var warning = style.getPropertyValue('--warning').trim();

  // ========== 图 1：整体结果分布（饼图）==========
  var chart1 = echarts.init(document.getElementById('chart-overall'), null, { renderer: 'svg' });
  chart1.setOption({
    animation: false,
    tooltip: { trigger: 'item', appendToBody: true, textStyle: { color: ink } },
    legend: {
      bottom: 0,
      textStyle: { color: muted, fontSize: 12 },
      itemWidth: 12, itemHeight: 12
    },
    series: [{
      type: 'pie',
      radius: ['45%', '72%'],
      center: ['50%', '45%'],
      label: {
        show: true,
        formatter: '{b}\n{c} 条 ({d}%)',
        color: ink,
        fontSize: 12
      },
      labelLine: { lineStyle: { color: rule } },
      data: [
        { value: 48, name: '通过', itemStyle: { color: accent2 } },
        { value: 7, name: '失败', itemStyle: { color: warning } }
      ]
    }]
  });
  window.addEventListener('resize', function() { chart1.resize(); });

  // ========== 图 2：各模块用例数与通过数（柱状图）==========
  var modules = ['ENV', 'PROJ', 'API', 'MAIN', 'TMPL', 'PERM', 'HAL', 'ERR', 'CTX', 'PAR', 'L3', 'E2E'];
  var totalCounts = [3, 5, 3, 9, 7, 6, 6, 6, 2, 1, 1, 6];
  var passCounts = [3, 5, 3, 9, 7, 6, 5, 4, 2, 1, 1, 2];

  var chart2 = echarts.init(document.getElementById('chart-modules'), null, { renderer: 'svg' });
  chart2.setOption({
    animation: false,
    tooltip: { trigger: 'axis', appendToBody: true, textStyle: { color: ink } },
    legend: {
      top: 0,
      textStyle: { color: muted, fontSize: 11 },
      itemWidth: 10, itemHeight: 10
    },
    grid: { left: '8%', right: '5%', top: '18%', bottom: '12%' },
    xAxis: {
      type: 'category',
      data: modules,
      axisLabel: { color: muted, fontSize: 10, rotate: 30 },
      axisLine: { lineStyle: { color: rule } }
    },
    yAxis: {
      type: 'value',
      axisLabel: { color: muted, fontSize: 11 },
      axisLine: { lineStyle: { color: rule } },
      splitLine: { lineStyle: { color: rule, type: 'dashed' } }
    },
    series: [
      {
        name: '总用例',
        type: 'bar',
        data: totalCounts,
        itemStyle: { color: accent, opacity: 0.4 },
        barGap: '10%',
        barCategoryGap: '40%'
      },
      {
        name: '通过',
        type: 'bar',
        data: passCounts,
        itemStyle: { color: accent2 },
        label: {
          show: true,
          position: 'top',
          color: ink,
          fontSize: 10
        }
      }
    ]
  });
  window.addEventListener('resize', function() { chart2.resize(); });

  // ========== 图 3：按优先级通过率（柱状图）==========
  var chart3 = echarts.init(document.getElementById('chart-priority'), null, { renderer: 'svg' });
  chart3.setOption({
    animation: false,
    tooltip: {
      trigger: 'axis',
      appendToBody: true,
      textStyle: { color: ink },
      formatter: function(params) {
        var p = params[0];
        return p.name + '<br/>通过：' + p.value[1] + ' / ' + p.value[2] + ' (' + p.value[3] + '%)';
      }
    },
    grid: { left: '10%', right: '8%', top: '10%', bottom: '12%' },
    xAxis: {
      type: 'category',
      data: ['P0 阻断', 'P1 核心', 'P2 辅助'],
      axisLabel: { color: muted, fontSize: 12 },
      axisLine: { lineStyle: { color: rule } }
    },
    yAxis: {
      type: 'value',
      max: 100,
      axisLabel: { color: muted, fontSize: 11, formatter: '{value}%' },
      axisLine: { lineStyle: { color: rule } },
      splitLine: { lineStyle: { color: rule, type: 'dashed' } }
    },
    series: [{
      type: 'bar',
      data: [
        { value: [0, 27, 31, 87], itemStyle: { color: warning } },
        { value: [1, 18, 21, 86], itemStyle: { color: accent } },
        { value: [2, 3, 3, 100], itemStyle: { color: accent2 } }
      ],
      barWidth: '45%',
      label: {
        show: true,
        position: 'top',
        color: ink,
        fontSize: 12,
        fontWeight: 700,
        formatter: function(p) {
          return p.value[3] + '%';
        }
      }
    }]
  });
  window.addEventListener('resize', function() { chart3.resize(); });

})();
