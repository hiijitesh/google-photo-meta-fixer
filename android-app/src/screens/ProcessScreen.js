import React, { useState } from 'react';
import { View, StyleSheet, ScrollView } from 'react-native';
import { Button, Text, Card, Title, ProgressBar } from 'react-native-paper';
import * as DocumentPicker from 'expo-document-picker';
import * as FileSystem from 'expo-file-system';
import { unzip } from 'react-native-zip-archive';
import { processExtractedFiles } from '../utils/processTakeout';

export default function ProcessScreen() {
  const [logs, setLogs] = useState([]);
  const [isProcessing, setIsProcessing] = useState(false);
  const [progress, setProgress] = useState(0);

  const addLog = (msg) => {
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
        return;
      }

      setIsProcessing(true);
      setLogs([]);
      setProgress(0.1);
      
      const assets = result.assets;
      addLog(`Selected ${assets.length} ZIP file(s).`);

      const targetDir = `${FileSystem.documentDirectory}extracted/`;
      
      // Ensure dir exists
      const dirInfo = await FileSystem.getInfoAsync(targetDir);
      if (!dirInfo.exists) {
        await FileSystem.makeDirectoryAsync(targetDir, { intermediates: true });
      }

      for (let i = 0; i < assets.length; i++) {
        const asset = assets[i];
        addLog(`Extracting ${asset.name}...`);
        try {
          await unzip(asset.uri, targetDir);
          addLog(`Extracted successfully.`);
        } catch (err) {
          addLog(`Extraction failed: ${err.message}`);
        }
        setProgress(0.1 + ((i + 1) / assets.length) * 0.4); // first 50% for extraction
      }

      addLog('Starting metadata merging...');
      await processExtractedFiles(targetDir, addLog, setProgress);
      setIsProcessing(false);

    } catch (error) {
      addLog(`Error: ${error.message}`);
      setIsProcessing(false);
    }
  };

  return (
    <View style={styles.container}>
      <Card style={styles.card}>
        <Card.Content>
          <Title>Takeout Processing</Title>
          <Text style={{ marginBottom: 10 }}>
            Select one or more Google Takeout ZIP files. The app will extract them and apply JSON metadata directly to the EXIF tags of your photos.
          </Text>
          <Button 
            mode="contained" 
            onPress={handlePickAndProcess}
            loading={isProcessing}
            disabled={isProcessing}
          >
            Select ZIP Files
          </Button>
          {isProcessing && (
             <ProgressBar progress={progress} style={{ marginTop: 15 }} />
          )}
        </Card.Content>
      </Card>

      <Card style={[styles.card, { flex: 1 }]}>
        <Card.Title title="Processing Log" />
        <Card.Content style={{ flex: 1 }}>
          <ScrollView style={styles.logArea}>
            {logs.map((log, i) => (
              <Text key={i} style={styles.logText}>{log}</Text>
            ))}
          </ScrollView>
        </Card.Content>
      </Card>
    </View>
  );
}

const styles = StyleSheet.create({
  container: {
    flex: 1,
    padding: 16,
    backgroundColor: '#f5f5f5',
  },
  card: {
    marginBottom: 16,
  },
  logArea: {
    backgroundColor: '#1e1e1e',
    padding: 10,
    borderRadius: 4,
    flex: 1,
  },
  logText: {
    color: '#00ff00',
    fontFamily: 'monospace',
    fontSize: 12,
    marginBottom: 4,
  }
});
