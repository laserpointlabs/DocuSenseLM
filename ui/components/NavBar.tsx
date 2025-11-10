'use client';

import { useAuth } from '@/contexts/AuthContext';
import { useRouter, usePathname } from 'next/navigation';

export default function NavBar() {
  const { isAuthenticated, user, logout } = useAuth();
  const router = useRouter();
  const pathname = usePathname();

  const handleLogout = () => {
    logout();
    router.push('/login');
  };

  // Don't show nav on login page
  if (pathname === '/login') {
    return null;
  }

  return (
    <nav className="bg-white shadow-sm border-b">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
        <div className="flex justify-between h-16">
          <div className="flex">
            <div className="flex-shrink-0 flex items-center">
              <h1 className="text-xl font-bold text-primary-700">NDA Dashboard</h1>
            </div>
            {isAuthenticated && (
              <div className="hidden sm:ml-6 sm:flex sm:space-x-8">
                <a
                  href="/dashboard"
                  className={`border-transparent text-gray-500 hover:border-gray-300 hover:text-gray-700 inline-flex items-center px-1 pt-1 border-b-2 text-sm font-medium ${
                    pathname === '/dashboard' ? 'border-primary-500 text-gray-900' : ''
                  }`}
                >
                  Dashboard
                </a>
                <a
                  href="/search"
                  className={`border-transparent text-gray-500 hover:border-gray-300 hover:text-gray-700 inline-flex items-center px-1 pt-1 border-b-2 text-sm font-medium ${
                    pathname === '/search' ? 'border-primary-500 text-gray-900' : ''
                  }`}
                >
                  Explore NDAs
                </a>
                <a
                  href="/answer"
                  className={`border-transparent text-gray-500 hover:border-gray-300 hover:text-gray-700 inline-flex items-center px-1 pt-1 border-b-2 text-sm font-medium ${
                    pathname === '/answer' ? 'border-primary-500 text-gray-900' : ''
                  }`}
                >
                  Ask Question
                </a>
                <a
                  href="/admin"
                  className={`border-transparent text-gray-500 hover:border-gray-300 hover:text-gray-700 inline-flex items-center px-1 pt-1 border-b-2 text-sm font-medium ${
                    pathname === '/admin' ? 'border-primary-500 text-gray-900' : ''
                  }`}
                >
                  Admin
                </a>
                <a
                  href="/roadmap"
                  className={`border-transparent text-gray-500 hover:border-gray-300 hover:text-gray-700 inline-flex items-center px-1 pt-1 border-b-2 text-sm font-medium ${
                    pathname === '/roadmap' ? 'border-primary-500 text-gray-900' : ''
                  }`}
                >
                  Roadmap
                </a>
              </div>
            )}
          </div>
          {isAuthenticated && (
            <div className="flex items-center space-x-4">
              <span className="text-sm text-gray-600">
                {user?.username} ({user?.role})
              </span>
              <button
                onClick={handleLogout}
                className="text-sm text-gray-500 hover:text-gray-700"
              >
                Logout
              </button>
            </div>
          )}
        </div>
      </div>
    </nav>
  );
}

