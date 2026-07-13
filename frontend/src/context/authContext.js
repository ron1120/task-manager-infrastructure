import { createContext } from 'react';

// Shared auth "bucket" — AuthProvider writes values; useAuth() reads them
export const AuthContext = createContext(null);
