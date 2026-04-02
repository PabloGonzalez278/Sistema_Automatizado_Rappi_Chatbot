import React from 'react';
import {
  LineChart, Line, BarChart, Bar, AreaChart, Area,
  XAxis, YAxis, CartesianGrid, Tooltip, Legend, ResponsiveContainer,
} from 'recharts';
import './ChartRenderer.css';

const COLORS = [
  '#FF441F', '#1a1a2e', '#2196F3', '#4CAF50', '#FF9800',
  '#9C27B0', '#00BCD4', '#E91E63', '#795548', '#607D8B',
];

function ChartRenderer({ chartData }) {
  if (!chartData || !chartData.data || chartData.data.length === 0) {
    return null;
  }

  const { type, title, data, series } = chartData;

  const renderChart = () => {
    const xKey = type === 'bar' ? 'name' : 'week';

    switch (type) {
      case 'line':
        return (
          <ResponsiveContainer width="100%" height={320}>
            <LineChart data={data} margin={{ top: 5, right: 20, left: 10, bottom: 5 }}>
              <CartesianGrid strokeDasharray="3 3" stroke="#f0f0f0" />
              <XAxis dataKey={xKey} tick={{ fontSize: 11 }} />
              <YAxis tick={{ fontSize: 11 }} />
              <Tooltip
                contentStyle={{ borderRadius: 8, border: '1px solid #eee', fontSize: 12 }}
              />
              <Legend wrapperStyle={{ fontSize: 12 }} />
              {series.map((s, i) => (
                <Line
                  key={s}
                  type="monotone"
                  dataKey={s}
                  stroke={COLORS[i % COLORS.length]}
                  strokeWidth={2}
                  dot={{ r: 3 }}
                  activeDot={{ r: 5 }}
                />
              ))}
            </LineChart>
          </ResponsiveContainer>
        );

      case 'bar':
        return (
          <ResponsiveContainer width="100%" height={320}>
            <BarChart data={data} margin={{ top: 5, right: 20, left: 10, bottom: 5 }}>
              <CartesianGrid strokeDasharray="3 3" stroke="#f0f0f0" />
              <XAxis dataKey={xKey} tick={{ fontSize: 10, angle: -30 }} interval={0} height={60} />
              <YAxis tick={{ fontSize: 11 }} />
              <Tooltip
                contentStyle={{ borderRadius: 8, border: '1px solid #eee', fontSize: 12 }}
              />
              <Legend wrapperStyle={{ fontSize: 12 }} />
              {series.map((s, i) => (
                <Bar
                  key={s}
                  dataKey={s}
                  fill={COLORS[i % COLORS.length]}
                  radius={[4, 4, 0, 0]}
                />
              ))}
            </BarChart>
          </ResponsiveContainer>
        );

      case 'area':
        return (
          <ResponsiveContainer width="100%" height={320}>
            <AreaChart data={data} margin={{ top: 5, right: 20, left: 10, bottom: 5 }}>
              <CartesianGrid strokeDasharray="3 3" stroke="#f0f0f0" />
              <XAxis dataKey={xKey} tick={{ fontSize: 11 }} />
              <YAxis tick={{ fontSize: 11 }} />
              <Tooltip
                contentStyle={{ borderRadius: 8, border: '1px solid #eee', fontSize: 12 }}
              />
              <Legend wrapperStyle={{ fontSize: 12 }} />
              {series.map((s, i) => (
                <Area
                  key={s}
                  type="monotone"
                  dataKey={s}
                  stroke={COLORS[i % COLORS.length]}
                  fill={COLORS[i % COLORS.length]}
                  fillOpacity={0.15}
                  strokeWidth={2}
                />
              ))}
            </AreaChart>
          </ResponsiveContainer>
        );

      default:
        return <p>Tipo de grafico no soportado: {type}</p>;
    }
  };

  return (
    <div className="chart-container">
      {title && <h4 className="chart-title">{title}</h4>}
      {renderChart()}
    </div>
  );
}

export default ChartRenderer;
