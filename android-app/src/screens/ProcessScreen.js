import React, { useState, useCallback, useRef } from 'react';
import { View, StyleSheet, ScrollView, Platform } from 'react-native';
import { Button, Text, Card, ProgressBar } from 'react-native-paper';
import * as DocumentPicker from 'expo-document-picker';
import * as FileSystem from 'expo-file-system/legacy';
import { unzip } from 'react-native-zip-archive';
import { processExtractedFiles } from '../utils/processTakeout';
import { useFocusEffect } from '@react-navigation/native';

const sleep = (ms = 10) => new Promise(resolve => setTimeout(resolve, ms));

export default function ProcessScreen() {
  const [logs, setLogs] = useState([]);
  const [isProcessing, setIsProcessing] = useState(false);
  const [progress, setProgress] = useState(0);

  useFocusEffect(
    useCallback(() => {
      return () => {
        // Clear the screen logs when navigating away
        if (!isProcessing) {
          setLogs([]);
          setProgress(0);
        }
      };
    }, [isProcessing])
  );

  const scrollViewRef = useRef(null);

  const addLog = (msg) => {
    console.log(`[UI LOG] ${msg}`);
    setLogs((prev) => [...prev, `[${new Date().toLocaleTimeString()}] ${msg}`]);
  };

  const handlePickAndProcess = async () => {
    try {
      const result = await DocumentPicker.getDocumentAsync({
        type: 'application/zip',
        copyToCacheDirectory: true,
        multiple: true,
      });

      if (result.canceled) {
        console.log('[DEBUG] Document picker canceled');
        return;
      }

      console.log('[DEBUG] Setting processing state to true');
      setIsProcessing(true);
      setLogs([]);
      setProgress(0.05);
      await sleep(50); // Force UI update before heavy lifting

      let outputDirUri = null;
      if (Platform.OS === 'android') {
        addLog('Please select a destination folder to save the clean photos...');
        await sleep(100);
        const outputPerm = await FileSystem.StorageAccessFramework.requestDirectoryPermissionsAsync();
        if (!outputPerm.granted) {
          addLog('Permission denied. Processing aborted.');
          setIsProcessing(false);
          return;
        }
        outputDirUri = outputPerm.directoryUri;
        addLog('Destination folder authorized successfully.');
      }

      const assets = result.assets;
      console.log(`[DEBUG] Selected ${assets.length} ZIP file(s). Asset 0 URI:`, assets[0]?.uri);
      addLog(`Selected ${assets.length} ZIP file(s).`);
      await sleep(10); // Force UI update

      const targetDir = `${FileSystem.documentDirectory}extracted/`;
      console.log(`[DEBUG] Target directory is: ${targetDir}`);
      addLog(`[DEBUG] Target directory is: ${targetDir}`);

      // Ensure dir exists
      console.log(`[DEBUG] Checking if directory exists...`);
      addLog(`[DEBUG] Checking if directory exists...`);
      const dirInfo = await FileSystem.getInfoAsync(targetDir);
      console.log(`[DEBUG] Directory exists: ${dirInfo.exists}`);
      if (!dirInfo.exists) {
        console.log(`[DEBUG] Creating directory...`);
        addLog(`[DEBUG] Creating directory...`);
        await FileSystem.makeDirectoryAsync(targetDir, { intermediates: true });
      }

      console.log(`[DEBUG] Starting asset loop...`);

      for (let i = 0; i < assets.length; i++) {
        const asset = assets[i];
        console.log(`[DEBUG] Processing asset ${i}: ${asset.name}`);
        addLog(`[DEBUG] Starting extraction for ${asset.name}...`);
        await sleep(10);
        try {
          console.log(`[DEBUG] Extracting native zip using react-native-zip-archive...`);
          addLog(`[DEBUG] Extracting native zip using react-native-zip-archive...`);
          await sleep(10);

          const zipPath = asset.uri.replace('file://', '');
          const destPath = targetDir.replace('file://', '');
          await unzip(zipPath, destPath);

          console.log(`[DEBUG] Extraction complete for ${asset.name}`);
          addLog(`Extracted successfully.`);
          await sleep(10);
        } catch (err) {
          console.error(`[DEBUG] Error during extraction:`, err);
          addLog(`Extraction failed: ${err.message}\nStack: ${err.stack}\nDetails: ${JSON.stringify(err)}`);
          await sleep(10);
        }
        setProgress(0.1 + ((i + 1) / assets.length) * 0.4); // first 50% for extraction
      }

      console.log(`[DEBUG] Starting metadata merging phase...`);
      addLog('[DEBUG] Extraction finished. Starting metadata merging...');
      await sleep(10);
      await processExtractedFiles(targetDir, addLog, setProgress, outputDirUri);
      console.log(`[DEBUG] processExtractedFiles complete. Setting isProcessing false.`);
      setIsProcessing(false);

    } catch (error) {
      console.error(`[DEBUG] Global handlePickAndProcess error:`, error);
      addLog(`[DEBUG] Global Error: ${error.message}\nStack: ${error.stack}\nDetails: ${JSON.stringify(error)}`);
      setIsProcessing(false);
    }
  };

  return (
    <View style={styles.container}>
      <Card style={styles.card}>
        <Card.Content>
          <Text style={styles.cardTitle}>Takeout Processing</Text>
          <Text style={styles.cardDesc}>
            Select Google Takeout ZIP files. The app will extract them and apply JSON metadata directly to the EXIF tags of your photos.
          </Text>
          {!isProcessing && (
            <Button
              mode="contained"
              onPress={handlePickAndProcess}
              style={styles.button}
              labelStyle={styles.buttonLabel}
            >
              Select ZIP Files
            </Button>
          )}
          {isProcessing && (
             <View>
               <ProgressBar progress={progress} color="#14B8A6" style={styles.progressBar} />
               <Text style={styles.progressText}>{Math.round(progress * 100)}% Complete</Text>
             </View>
          )}
        </Card.Content>
      </Card>

      <View style={[styles.card, { flex: 1, minHeight: 300, backgroundColor: '#090D16', overflow: 'hidden' }]}>
        <Text style={[styles.cardTitle, { paddingHorizontal: 16, paddingTop: 16, color: '#94A3B8', fontSize: 13, textTransform: 'uppercase', letterSpacing: 1 }]}>Processing Log</Text>
        <ScrollView
          ref={scrollViewRef}
          onContentSizeChange={() => scrollViewRef.current?.scrollToEnd({ animated: true })}
          style={styles.logArea}
          contentContainerStyle={{ paddingHorizontal: 16, paddingBottom: 16 }}
        >
          {logs.map((log, i) => (
            <Text key={i} style={styles.logText}>{log}</Text>
          ))}
        </ScrollView>
      </View>
    </View>
  );
}

const styles = StyleSheet.create({
  container: {
    flex: 1,
    padding: 16,
    backgroundColor: '#0F172A', // Slate 900
  },
  card: {
    backgroundColor: '#1E293B', // Slate 800
    borderWidth: 1,
    borderColor: '#334155', // Slate 700
    borderRadius: 12,
    marginBottom: 16,
  },
  cardTitle: {
    fontSize: 18,
    fontWeight: 'bold',
    color: '#F8FAFC',
    marginBottom: 8,
  },
  cardDesc: {
    fontSize: 13,
    color: '#94A3B8',
    lineHeight: 18,
    marginBottom: 16,
  },
  button: {
    backgroundColor: '#6366F1', // Indigo 500
    borderRadius: 8,
  },
  buttonLabel: {
    fontSize: 14,
    fontWeight: 'bold',
    color: '#FFFFFF',
  },
  progressBar: {
    height: 6,
    borderRadius: 3,
    marginTop: 15,
  },
  progressText: {
    color: '#14B8A6',
    fontSize: 12,
    fontWeight: 'bold',
    textAlign: 'right',
    marginTop: 6,
  },
  logArea: {
    backgroundColor: '#090D16', // Deep dark theme for console logs
    flex: 1,
  },
  logText: {
    color: '#38BDF8', // Cool cyan/blue for log data
    fontFamily: Platform.OS === 'ios' ? 'Courier' : 'monospace',
    fontSize: 12,
    lineHeight: 16,
    marginBottom: 4,
  }
});
