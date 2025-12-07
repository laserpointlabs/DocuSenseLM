import React from 'react';

export const LoadingScreen = () => {
  return (
    <div className="flex flex-col items-center justify-center h-screen bg-slate-50">
      <div className="relative w-16 h-16 mb-4">
        <div className="absolute top-0 left-0 w-full h-full border-4 border-slate-200 rounded-full"></div>
        <div className="absolute top-0 left-0 w-full h-full border-4 border-blue-600 rounded-full border-t-transparent animate-spin"></div>
      </div>
      <h2 className="text-xl font-semibold text-slate-700">Initializing NDA Tool...</h2>
      <p className="text-slate-500 mt-2">Starting local services</p>
    </div>
  );
};

