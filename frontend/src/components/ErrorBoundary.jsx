import React from 'react';
import { AlertTriangle, RefreshCw } from 'lucide-react';

export default class ErrorBoundary extends React.Component {
  constructor(props) {
    super(props);
    this.state = { hasError: false, error: null };
  }

  static getDerivedStateFromError(error) {
    return { hasError: true, error };
  }

  render() {
    if (this.state.hasError) {
      return (
        <div className="flex flex-col items-center justify-center h-full p-8 text-center bg-white rounded-xl shadow-sm border border-slate-100 max-w-lg mx-auto mt-20">
          <div className="w-16 h-16 bg-red-100 text-red-600 flex items-center justify-center rounded-full mb-4">
            <AlertTriangle size={32} />
          </div>
          <h2 className="text-xl font-bold text-slate-800 mb-2">משהו השתבש</h2>
          <p className="text-slate-600 mb-6 text-sm">{this.state.error?.message || 'שגיאה לא צפויה התרחשתה במערכת.'}</p>
          <button 
            onClick={() => window.location.reload()}
            className="flex items-center gap-2 bg-indigo-600 text-white px-4 py-2 rounded-lg font-medium hover:bg-indigo-700 transition-colors"
          >
            <RefreshCw size={16} /> טען מחדש
          </button>
        </div>
      );
    }
    return this.props.children;
  }
}
