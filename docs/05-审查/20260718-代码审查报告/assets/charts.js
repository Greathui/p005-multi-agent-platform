(function() {
  var style = getComputedStyle(document.documentElement);
  var accent = style.getPropertyValue('--accent').trim();
  var accent2 = style.getPropertyValue('--accent2').trim();
  var ink = style.getPropertyValue('--ink').trim();
  var muted = style.getPropertyValue('--muted').trim();
  var rule = style.getPropertyValue('--rule').trim();
  var bg2 = style.getPropertyValue('--bg2').trim();
  var success = style.getPropertyValue('--success').trim();
  var warning = style.getPropertyValue('--warning').trim();
  var danger = style.getPropertyValue('--danger').trim();
  var info = style.getPropertyValue('--info').trim();

  // --- Chart 1: 总体实现状态 饼图 ---
  var pieEl = document.getElementById('chart-pie');
  if (pieEl) {
    var pieChart = echarts.init(pieEl, null, { renderer: 'svg' });
    pieChart.setOption({
      animation: false,
      tooltip: {
        trigger: 'item',
        appendToBody: true,
        formatter: '{b}: {c} 项 ({d}%)'
      },
      legend: {
        bottom: 5,
        left: 'center',
        itemWidth: 12,
        itemHeight: 12,
        textStyle: { color: muted, fontSize: 12 }
      },
      series: [{
        type: 'pie',
        radius: ['42%', '68%'],
        center: ['50%', '44%'],
        avoidLabelOverlap: true,
        itemStyle: {
          borderRadius: 6,
          borderColor: bg2,
          borderWidth: 2
        },
        label: {
          show: true,
          formatter: '{b}\n{c} 项',
          color: ink,
          fontSize: 12,
          fontWeight: 600
        },
        labelLine: { length: 12, length2: 10 },
        data: [
          { value: 36, name: '完全实现', itemStyle: { color: success } },
          { value: 3, name: '部分实现', itemStyle: { color: warning } },
          { value: 0, name: '未实现', itemStyle: { color: danger } }
        ]
      }]
    });
    window.addEventListener('resize', function() { pieChart.resize(); });
  }

  // --- Chart 2: 各模块功能实现数量 柱状图 ---
  var barEl = document.getElementById('chart-bar');
  if (barEl) {
    var barChart = echarts.init(barEl, null, { renderer: 'svg' });
    barChart.setOption({
      animation: false,
      tooltip: {
        trigger: 'axis',
        appendToBody: true,
        axisPointer: { type: 'shadow' },
        formatter: function(params) {
          var s = params[0].name + '<br/>';
          params.forEach(function(p) {
            s += p.marker + p.seriesName + ': ' + p.value + ' 项<br/>';
          });
          return s;
        }
      },
      legend: {
        bottom: 2,
        left: 'center',
        itemWidth: 12,
        itemHeight: 12,
        textStyle: { color: muted, fontSize: 11 }
      },
      grid: {
        left: 8,
        right: 16,
        top: 18,
        bottom: 42,
        containLabel: true
      },
      xAxis: {
        type: 'category',
        data: ['核心对话', '项目系统', '智能体', '多智能体', '工具系统', '文件浏览', '权限系统', 'UI细节'],
        axisLabel: {
          color: muted,
          fontSize: 10,
          interval: 0,
          rotate: 0
        },
        axisLine: { lineStyle: { color: rule } },
        axisTick: { show: false }
      },
      yAxis: {
        type: 'value',
        minInterval: 1,
        axisLabel: { color: muted, fontSize: 10 },
        splitLine: { lineStyle: { color: rule, type: 'dashed' } },
        axisLine: { show: false }
      },
      series: [
        {
          name: '完全实现',
          type: 'bar',
          stack: 'total',
          barWidth: '52%',
          itemStyle: { color: success, borderRadius: [0, 0, 0, 0] },
          data: [6, 3, 3, 5, 7, 5, 8, 4]
        },
        {
          name: '部分实现',
          type: 'bar',
          stack: 'total',
          barWidth: '52%',
          itemStyle: { color: warning, borderRadius: [4, 4, 0, 0] },
          data: [0, 0, 1, 1, 0, 0, 0, 0]
        }
      ]
    });
    window.addEventListener('resize', function() { barChart.resize(); });
  }
})();
