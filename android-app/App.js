import React from 'react';
import { NavigationContainer } from '@react-navigation/native';
import { createNativeStackNavigator } from '@react-navigation/native-stack';
import { Provider as PaperProvider, MD3LightTheme as DefaultTheme } from 'react-native-paper';

import HomeScreen from './src/screens/HomeScreen';
import WebViewScreen from './src/screens/WebViewScreen';
import ProcessScreen from './src/screens/ProcessScreen';

const Stack = createNativeStackNavigator();

const theme = {
  ...DefaultTheme,
  colors: {
    ...DefaultTheme.colors,
    primary: '#1976D2',
    secondary: '#424242',
  },
};

export default function App() {
  return (
    <PaperProvider theme={theme}>
      <NavigationContainer>
        <Stack.Navigator initialRouteName="Home">
          <Stack.Screen 
            name="Home" 
            component={HomeScreen} 
            options={{ title: 'Google Photos Cleaner' }} 
          />
          <Stack.Screen 
            name="WebView" 
            component={WebViewScreen} 
            options={{ title: 'Export Metadata' }} 
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
