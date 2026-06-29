import React, { useRef, useState } from 'react';
import { View, StyleSheet, Alert, Platform } from 'react-native';
import { WebView } from 'react-native-webview';
import * as FileSystem from 'expo-file-system';
import { userScript } from '../userscript';

export default function WebViewScreen({ navigation }) {
  const webviewRef = useRef(null);
  const [loading, setLoading] = useState(true);

  const injectedJavaScript = `
    // Inject the main userscript
    ${userScript}

    // Intercept CSV downloads
    (function() {
      const originalCreateObjectURL = URL.createObjectURL;
      URL.createObjectURL = function(obj) {
        if (obj instanceof Blob && (obj.type === 'text/csv' || obj.type === 'application/json')) {
          const reader = new FileReader();
          reader.onload = function() {
             window.ReactNativeWebView.postMessage(JSON.stringify({
               type: 'FILE_EXPORT',
               mime: obj.type,
               data: reader.result
             }));
          }
          reader.readAsText(obj);
        }
        return originalCreateObjectURL(obj);
      };

      // Also intercept anchor clicks just in case
      document.addEventListener('click', function(e) {
        if (e.target.tagName === 'A' && e.target.download && e.target.href.startsWith('blob:')) {
           // Handled by URL.createObjectURL intercept, but could add fallback herej
        }
      }, true);
    })();
    true;
  `;

  const onMessage = async (event) => {
    try {
      const message = JSON.parse(event.nativeEvent.data);
      if (message.type === 'FILE_EXPORT') {
        const isCsv = message.mime === 'text/csv';
        const extension = isCsv ? '.csv' : '.json';
        const filename = `gptk_export_${new Date().getTime()}${extension}`;

        // Define path
        const fileUri = `${FileSystem.documentDirectory}${filename}`;

        // Save to app storage
        await FileSystem.writeAsStringAsync(fileUri, message.data, {
          encoding: FileSystem.EncodingType.UTF8,
        });

        Alert.alert(
          'Export Successful',
          `Saved to ${filename}\n\nYou can now use this in the Takeout Processor.`,
          [{ text: 'OK' }]
        );
      }
    } catch (e) {
      console.warn("Could not parse message from WebView: ", e);
    }
  };

  return (
    <View style={styles.container}>
      <WebView
        ref={webviewRef}
        source={{ uri: 'https://photos.google.com/' }}
        injectedJavaScript={injectedJavaScript}
        onMessage={onMessage}
        sharedCookiesEnabled={true}
        thirdPartyCookiesEnabled={true}
        onLoadEnd={() => setLoading(false)}
        style={styles.webview}
      />
    </View>
  );
}

const styles = StyleSheet.create({
  container: {
    flex: 1,
  },
  webview: {
    flex: 1,
  },
});
