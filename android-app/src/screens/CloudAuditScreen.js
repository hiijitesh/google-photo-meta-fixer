import React, { useState, useRef, useEffect } from 'react';
import { View, StyleSheet, ScrollView, TouchableOpacity, TextInput, Alert, Platform, ActivityIndicator } from 'react-native';
import { Text, Button, Card, ProgressBar, SegmentedButtons } from 'react-native-paper';
import { MaterialCommunityIcons } from '@expo/vector-icons';
import * as DocumentPicker from 'expo-document-picker';
import * as FileSystem from 'expo-file-system/legacy';
import * as WebBrowser from 'expo-web-browser';

WebBrowser.maybeCompleteAuthSession();

const sleep = (ms = 10) => new Promise(resolve => setTimeout(resolve, ms));

export default function CloudAuditScreen() {
  const [tabValue, setTabValue] = useState('api');
  const [clientId, setClientId] = useState('');
  const [isScanning, setIsScanning] = useState(false);
  const [progress, setProgress] = useState(0);
  const [logs, setLogs] = useState([]);
  const [csvSummary, setCsvSummary] = useState(null);
  
  const scrollViewRef = useRef(null);
  const logHistoryRef = useRef([]);

  const addLog = (msg) => {
    const formatted = `[${new Date().toLocaleTimeString()}] ${msg}`;
    console.log(`[AUDIT LOG] ${msg}`);
    logHistoryRef.current.push(formatted);
    setLogs([...logHistoryRef.current]);
  };

  const handleCsvImport = async () => {
    try {
      const result = await DocumentPicker.getDocumentAsync({
        type: 'text/csv',
        copyToCacheDirectory: true,
      });

      if (result.canceled) {
        console.log('[DEBUG] CSV Picker canceled');
        return;
      }

      const asset = result.assets[0];
      addLog(`Selected CSV: ${asset.name}`);
      
      const csvContent = await FileSystem.readAsStringAsync(asset.uri);
      addLog('Parsing CSV records...');
      
      // Simple CSV parsing
      const lines = csvContent.split(/\r?\n/);
      if (lines.length <= 1) {
        throw new Error('CSV file is empty or invalid.');
      }

      const headers = lines[0].split(',').map(h => h.replace(/^"|"$/g, '').trim());
      const sizeIndex = headers.indexOf('sizeBytes');
      const nameIndex = headers.indexOf('fileName');
      
      if (sizeIndex === -1 && headers.indexOf('size') === -1) {
        addLog('Warning: Could not find sizeBytes or size column. Double check CSV format.');
      }

      let totalSize = 0;
      let recordCount = 0;
      let largeFiles = [];

      for (let i = 1; i < lines.length; i++) {
        const line = lines[i];
        if (!line.trim()) continue;
        const values = line.split(/,(?=(?:(?:[^"]*"){2})*[^"]*$)/).map(v => v.replace(/^"|"$/g, '').trim());
        
        recordCount++;
        const sizeVal = parseFloat(values[sizeIndex !== -1 ? sizeIndex : 0]);
        if (!isNaN(sizeVal)) {
          totalSize += sizeVal;
          const fileName = values[nameIndex !== -1 ? nameIndex : 1] || 'Unknown';
          largeFiles.push({ name: fileName, size: sizeVal });
        }
      }

      // Sort by size desc, get top 3
      largeFiles.sort((a, b) => b.size - a.size);
      const topLarge = largeFiles.slice(0, 3);

      const totalMb = (totalSize / (1024 * 1024)).toFixed(2);
      const totalGb = (totalSize / (1024 * 1024 * 1024)).toFixed(2);

      setCsvSummary({
        fileName: asset.name,
        count: recordCount,
        sizeMb: totalMb,
        sizeGb: totalGb,
        topLarge
      });

      addLog(`CSV Parsed successfully. Found ${recordCount} records. Total size: ${totalGb} GB.`);

      // Save to app internal storage as the default catalog
      const localDest = `${FileSystem.documentDirectory}gptk_export.csv`;
      await FileSystem.writeAsStringAsync(localDest, csvContent);
      addLog('Registered CSV metadata as default database.');

    } catch (err) {
      console.error(err);
      addLog(`Error parsing CSV: ${err.message}`);
      Alert.alert('Import Failed', err.message);
    }
  };

  const handleApiScan = async () => {
    if (!clientId.trim()) {
      Alert.alert('Configuration Required', 'Please enter your Google OAuth Client ID to start native scanning.');
      return;
    }

    try {
      setIsScanning(true);
      logHistoryRef.current = [];
      setLogs([]);
      setProgress(0);
      addLog('Initiating secure OAuth sign-in flow...');

      const redirectUri = 'google-photos-cleaner://oauth';
      const authUrl = `https://accounts.google.com/o/oauth2/v2/auth?` + 
        `client_id=${encodeURIComponent(clientId.trim())}&` +
        `redirect_uri=${encodeURIComponent(redirectUri)}&` +
        `response_type=token&` +
        `scope=https://www.googleapis.com/auth/photoslibrary.readonly`;

      console.log('[DEBUG] Opening Auth Session Url:', authUrl);
      const authResult = await WebBrowser.openAuthSessionAsync(authUrl, redirectUri);
      console.log('[DEBUG] Auth result: ', authResult);

      if (authResult.type !== 'success') {
        addLog('Authentication was canceled or failed.');
        setIsScanning(false);
        return;
      }

      // Parse token from hash fragment in the redirect URL
      const redirectUrl = authResult.url;
      const params = {};
      const hash = redirectUrl.split('#')[1];
      if (hash) {
        hash.split('&').forEach(p => {
          const parts = p.split('=');
          params[parts[0]] = decodeURIComponent(parts[1]);
        });
      }

      const accessToken = params.access_token;
      if (!accessToken) {
        addLog('Failed to retrieve Access Token from Google OAuth redirect.');
        setIsScanning(false);
        return;
      }

      addLog('Signed in successfully! Fetching media items...');
      await sleep(50);

      let nextPageToken = null;
      let itemsList = [];
      let pageCount = 0;
      let totalBytesCalculated = 0;

      // Stage 1: List Media Items
      do {
        pageCount++;
        addLog(`Fetching media items list (Page ${pageCount})...`);
        setProgress(0.1 + Math.min(pageCount * 0.05, 0.3)); // Max 40% for page listing
        await sleep(10);

        let url = 'https://photoslibrary.googleapis.com/v1/mediaItems?pageSize=100';
        if (nextPageToken) {
          url += `&pageToken=${nextPageToken}`;
        }

        const listRes = await fetch(url, {
          headers: { Authorization: `Bearer ${accessToken}` }
        });

        if (!listRes.ok) {
          const errorMsg = await listRes.text();
          throw new Error(`Google API returned error: ${errorMsg}`);
        }

        const data = await listRes.json();
        if (data.mediaItems && data.mediaItems.length > 0) {
          itemsList = itemsList.concat(data.mediaItems);
          addLog(`Listed ${itemsList.length} total items.`);
        }
        nextPageToken = data.nextPageToken;
      } while (nextPageToken && itemsList.length < 500); // Caps listing to 500 items for safety / demo limits

      addLog(`Listed ${itemsList.length} items. Starting file size queries (HEAD requests)...`);
      await sleep(50);

      // Stage 2: Fetch sizes via HEAD requests
      const csvRows = ['fileName,takenAt,sizeBytes,mimeType,productUrl'];
      
      for (let i = 0; i < itemsList.length; i++) {
        if (i % 5 === 0) {
          setProgress(0.4 + (i / itemsList.length) * 0.5); // 40% to 90% for size audits
          await sleep(10);
        }

        const item = itemsList[i];
        const isVideo = item.mimeType && item.mimeType.startsWith('video/');
        const queryUrl = isVideo ? `${item.baseUrl}=dv` : item.baseUrl;
        
        try {
          // Perform HEAD request to read content-length
          const headRes = await fetch(queryUrl, { method: 'HEAD' });
          const sizeBytes = headRes.headers.get('content-length') || '0';
          const sizeInt = parseInt(sizeBytes, 10);
          totalBytesCalculated += sizeInt;

          // Push to CSV row
          const cleanName = item.filename.replace(/"/g, '""');
          csvRows.push(`"${cleanName}","${item.mediaMetadata.creationTime}",${sizeBytes},"${item.mimeType}","${item.productUrl}"`);
          
          if (i < 10 || isVideo || sizeInt > 10 * 1024 * 1024) {
            const sizeDisplay = (sizeInt / (1024 * 1024)).toFixed(1);
            addLog(`Audited: ${item.filename} (${sizeDisplay} MB)`);
          }
        } catch (itemErr) {
          console.warn(`Failed to HEAD ${item.filename}:`, itemErr);
          csvRows.push(`"${item.filename.replace(/"/g, '""')}","${item.mediaMetadata.creationTime}",0,"${item.mimeType}","${item.productUrl}"`);
        }
      }

      // Stage 3: Export CSV File
      addLog('Compiling audit results...');
      setProgress(0.95);
      await sleep(10);

      const finalCsvText = csvRows.join('\n');
      const csvFilename = `cloud_audit_${new Date().getTime()}.csv`;

      // Save locally
      const localUri = `${FileSystem.documentDirectory}gptk_export.csv`;
      await FileSystem.writeAsStringAsync(localUri, finalCsvText);
      addLog('Metadata registered inside app database.');

      // Prompt to save to a SAF public folder if authorized
      let outputDirUri = null;
      if (Platform.OS === 'android') {
        addLog('Requesting storage folder to save the CSV report...');
        const outputPerm = await FileSystem.StorageAccessFramework.requestDirectoryPermissionsAsync();
        if (outputPerm.granted) {
          const safFileUri = await FileSystem.StorageAccessFramework.createFileAsync(
            outputPerm.directoryUri,
            csvFilename,
            'text/csv'
          );
          await FileSystem.StorageAccessFramework.writeAsStringAsync(safFileUri, finalCsvText, {
            encoding: FileSystem.EncodingType.UTF8
          });
          addLog(`CSV report saved in folder: ${csvFilename}`);
        } else {
          addLog('Save aborted: Permission to folder denied.');
        }
      }

      setProgress(1.0);
      const totalGb = (totalBytesCalculated / (1024 * 1024 * 1024)).toFixed(2);
      addLog(`Scan complete! Audited ${itemsList.length} items. Total size: ${totalGb} GB.`);
      setIsScanning(false);

    } catch (err) {
      console.error(err);
      addLog(`Fatal Error: ${err.message}`);
      setIsScanning(false);
      Alert.alert('Scan Failed', err.message);
    }
  };

  return (
    <View style={styles.container}>
      <Card style={styles.card}>
        <Card.Content style={{ padding: 12 }}>
          <SegmentedButtons
            value={tabValue}
            onValueChange={setTabValue}
            buttons={[
              { value: 'api', label: 'Auto API Scan', icon: 'cloud-sync' },
              { value: 'csv', label: 'Manual CSV', icon: 'file-import' },
            ]}
            theme={{ colors: { primary: '#14B8A6' } }}
          />
        </Card.Content>
      </Card>

      {tabValue === 'api' ? (
        <Card style={styles.card}>
          <Card.Content>
            <Text style={styles.cardTitle}>Auto Cloud Scan (API)</Text>
            <Text style={styles.cardDesc}>
              Connect directly to the Google Photos Library API to automatically scan file metadata. No WebView login needed.
            </Text>

            <TextInput
              style={styles.input}
              placeholder="Enter Google OAuth Client ID"
              placeholderTextColor="#475569"
              value={clientId}
              onChangeText={setClientId}
              autoCapitalize="none"
              autoCorrect={false}
            />
            
            <Text style={styles.setupHint}>
              * Redirect URI in Google Cloud Console must be set to:{'\n'}
              <Text style={{ fontWeight: 'bold', color: '#6366F1' }}>google-photos-cleaner://oauth</Text>
            </Text>

            {!isScanning && (
              <Button
                mode="contained"
                onPress={handleApiScan}
                style={styles.apiButton}
                labelStyle={styles.buttonLabel}
              >
                Scan Google Photos Library
              </Button>
            )}

            {isScanning && (
              <View style={{ marginTop: 8 }}>
                <ProgressBar progress={progress} color="#14B8A6" style={styles.progressBar} />
                <Text style={styles.progressText}>{Math.round(progress * 100)}% Audited</Text>
              </View>
            )}
          </Card.Content>
        </Card>
      ) : (
        <Card style={styles.card}>
          <Card.Content>
            <Text style={styles.cardTitle}>Kiwi Exporter CSV</Text>
            <Text style={styles.cardDesc}>
              Use Chrome Custom Extensions (like Tampermonkey) on Kiwi Browser to run the Photos Toolkit userscript, then import the exported CSV file below.
            </Text>

            <Button
              mode="contained"
              onPress={handleCsvImport}
              style={[styles.apiButton, { backgroundColor: '#14B8A6' }]}
              labelStyle={styles.buttonLabel}
              icon="file-upload"
            >
              Select CSV File
            </Button>

            {csvSummary && (
              <View style={styles.summaryContainer}>
                <Text style={styles.summaryTitle}>Imported Database Summary</Text>
                <View style={styles.summaryRow}>
                  <Text style={styles.summaryLabel}>Total Photos/Videos:</Text>
                  <Text style={styles.summaryValue}>{csvSummary.count}</Text>
                </View>
                <View style={styles.summaryRow}>
                  <Text style={styles.summaryLabel}>Total Storage Volume:</Text>
                  <Text style={styles.summaryValue}>{csvSummary.sizeGb} GB ({csvSummary.sizeMb} MB)</Text>
                </View>
                
                <Text style={[styles.summaryLabel, { marginTop: 12, marginBottom: 6 }]}>Top Storage Consuming Files:</Text>
                {csvSummary.topLarge.map((file, i) => (
                  <Text key={i} style={styles.largeFileRow} numberOfLines={1}>
                    • {file.name} ({(file.size / (1024 * 1024)).toFixed(1)} MB)
                  </Text>
                ))}
              </View>
            )}
          </Card.Content>
        </Card>
      )}

      {/* Terminal logs window */}
      <View style={[styles.card, { flex: 1, backgroundColor: '#090D16', overflow: 'hidden' }]}>
        <Text style={[styles.cardTitle, { paddingHorizontal: 16, paddingTop: 16, color: '#94A3B8', fontSize: 13, textTransform: 'uppercase', letterSpacing: 1 }]}>
          Console Output
        </Text>
        <ScrollView
          ref={scrollViewRef}
          onContentSizeChange={() => scrollViewRef.current?.scrollToEnd({ animated: true })}
          style={styles.logArea}
          contentContainerStyle={{ paddingHorizontal: 16, paddingBottom: 16 }}
        >
          {logs.length === 0 ? (
            <Text style={[styles.logText, { color: '#475569', fontStyle: 'italic' }]}>Ready for action. Waiting for scan or import...</Text>
          ) : (
            logs.map((log, i) => <Text key={i} style={styles.logText}>{log}</Text>)
          )}
        </ScrollView>
      </View>
    </View>
  );
}

const styles = StyleSheet.create({
  container: {
    flex: 1,
    padding: 16,
    backgroundColor: '#0A0F1D',
  },
  card: {
    backgroundColor: '#131929',
    borderWidth: 1,
    borderColor: '#1E293B',
    borderRadius: 12,
    marginBottom: 16,
  },
  cardTitle: {
    fontSize: 16,
    fontWeight: 'bold',
    color: '#FFFFFF',
    marginBottom: 8,
  },
  cardDesc: {
    fontSize: 12,
    color: '#64748B',
    lineHeight: 18,
    marginBottom: 16,
  },
  input: {
    height: 48,
    backgroundColor: '#090D16',
    borderWidth: 1,
    borderColor: '#1E293B',
    borderRadius: 8,
    paddingHorizontal: 12,
    color: '#FFFFFF',
    fontSize: 13,
    marginBottom: 12,
  },
  setupHint: {
    fontSize: 11,
    color: '#64748B',
    lineHeight: 16,
    marginBottom: 16,
  },
  apiButton: {
    backgroundColor: '#6366F1',
    borderRadius: 8,
  },
  buttonLabel: {
    fontSize: 13,
    fontWeight: 'bold',
    color: '#FFFFFF',
    paddingVertical: 2,
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
  summaryContainer: {
    marginTop: 16,
    padding: 12,
    backgroundColor: '#090D16',
    borderWidth: 1,
    borderColor: '#1E293B',
    borderRadius: 8,
  },
  summaryTitle: {
    fontSize: 13,
    fontWeight: 'bold',
    color: '#14B8A6',
    marginBottom: 8,
    textTransform: 'uppercase',
  },
  summaryRow: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    paddingVertical: 4,
  },
  summaryLabel: {
    fontSize: 12,
    color: '#64748B',
  },
  summaryValue: {
    fontSize: 12,
    color: '#FFFFFF',
    fontWeight: '600',
  },
  largeFileRow: {
    fontSize: 12,
    color: '#94A3B8',
    paddingVertical: 2,
  },
  logArea: {
    backgroundColor: '#090D16',
    flex: 1,
  },
  logText: {
    color: '#38BDF8',
    fontFamily: Platform.OS === 'ios' ? 'Courier' : 'monospace',
    fontSize: 12,
    lineHeight: 16,
    marginBottom: 4,
  },
});
