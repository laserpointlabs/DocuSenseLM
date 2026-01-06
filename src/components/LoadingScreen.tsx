
import { useState, useEffect } from 'react';

export const LoadingScreen = () => {
  const [statusMessage, setStatusMessage] = useState('Initializing DocuSenseLM...');
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    console.log('LoadingScreen: Component mounted');

    // Set up IPC listeners using the proper contextBridge API
    const unsubscribers: Array<() => void> = [];

    if (window.electronAPI?.handleStartupStatus) {
      console.log('LoadingScreen: Setting up startup status handler');
      const unsub = window.electronAPI.handleStartupStatus((status: string) => {
        console.log('LoadingScreen: Received status update:', status);
        setStatusMessage(status);
      });
      if (typeof unsub === 'function') unsubscribers.push(unsub);
    } else {
      console.log('LoadingScreen: electronAPI.handleStartupStatus not available');
    }

    if (window.electronAPI?.handlePythonReady) {
      console.log('LoadingScreen: Setting up python ready handler');
      const unsub = window.electronAPI.handlePythonReady(() => {
        console.log('LoadingScreen: Backend ready signal received');
        setStatusMessage('Ready!');
      });
      if (typeof unsub === 'function') unsubscribers.push(unsub);
    } else {
      console.log('LoadingScreen: electronAPI.handlePythonReady not available');
    }

    if (window.electronAPI?.handlePythonError) {
      console.log('LoadingScreen: Setting up python error handler');
      const unsub = window.electronAPI.handlePythonError((error: string) => {
        console.error('LoadingScreen: Error received:', error);
        setError(error);
        setStatusMessage('Startup failed');
      });
      if (typeof unsub === 'function') unsubscribers.push(unsub);
    } else {
      console.log('LoadingScreen: electronAPI.handlePythonError not available');
    }

    return () => {
      for (const unsub of unsubscribers) {
        try {
          unsub();
        } catch {
          // ignore
        }
      }
    };
  }, []);

  return (
    <div className="flex flex-col items-center justify-center h-screen bg-slate-50">
      <div className="relative w-16 h-16 mb-4">
        <div className="absolute top-0 left-0 w-full h-full border-4 border-slate-200 rounded-full"></div>
        <div className={`absolute top-0 left-0 w-full h-full border-4 border-blue-600 rounded-full border-t-transparent animate-spin ${error ? 'border-red-600' : ''}`}></div>
      </div>
      <h2 className="text-xl font-semibold text-slate-700">
        {error ? 'Startup Error' : 'Initializing DocuSenseLM...'}
      </h2>
      <p className={`mt-2 text-center max-w-md ${error ? 'text-red-600' : 'text-slate-500'}`}>
        {error || statusMessage}
      </p>
      {error && (
        <div className="mt-4 p-4 bg-red-50 border border-red-200 rounded-lg max-w-md">
          <p className="text-sm text-red-700">
            The application failed to start. Please check the console for more details or try restarting the application.
          </p>
        </div>
      )}
    </div>
  );
};
