import React from 'react';
import { NavigationContainer } from '@react-navigation/native';
import { createNativeStackNavigator } from '@react-navigation/native-stack';
import { Provider as PaperProvider, MD3DarkTheme } from 'react-native-paper';

import HomeScreen from './src/screens/HomeScreen';
import CloudAuditScreen from './src/screens/CloudAuditScreen';
import ProcessScreen from './src/screens/ProcessScreen';

const Stack = createNativeStackNavigator();

const theme = {
  ...MD3DarkTheme,
  colors: {
    ...MD3DarkTheme.colors,
    primary: '#6366F1', // Indigo
    secondary: '#14B8A6', // Cyan
    background: '#0F172A',
    surface: '#1E293B',
  },
};

export default function App() {
  return (
    <PaperProvider theme={theme}>
      <NavigationContainer>
        <Stack.Navigator 
          initialRouteName="Home"
          screenOptions={{
            headerStyle: {
              backgroundColor: '#0A0F1D', // Midnight blue
            },
            headerTintColor: '#F8FAFC', // Slate 50
            headerTitleStyle: {
              fontWeight: 'bold',
            },
            contentStyle: {
              backgroundColor: '#0A0F1D', // Midnight blue
            }
          }}
        >
          <Stack.Screen 
            name="Home" 
            component={HomeScreen} 
            options={{ title: 'Photos Cleaner' }} 
          />
          <Stack.Screen 
            name="CloudAudit" 
            component={CloudAuditScreen} 
            options={{ title: 'Cloud Audit Center' }} 
          />
          <Stack.Screen 
            name="Process" 
            component={ProcessScreen} 
            options={{ title: 'Process Takeout' }} 
          />
        </Stack.Navigator>
      </NavigationContainer>
    </PaperProvider>
  );
}
