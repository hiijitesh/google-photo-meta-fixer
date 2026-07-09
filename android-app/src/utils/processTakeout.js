import * as FileSystem from 'expo-file-system/legacy';
import piexif from 'piexifjs';

// Walk a directory recursively and return all files
async function walkDir(dirUri) {
  console.log(`[DEBUG] walkDir scanning: ${dirUri}`);
  let results = [];
  const dirInfo = await FileSystem.getInfoAsync(dirUri);
  if (!dirInfo.isDirectory) {
    return [dirUri];
  }

  const contents = await FileSystem.readDirectoryAsync(dirUri);
  console.log(`[DEBUG] Directory ${dirUri} contains ${contents.length} items`);
  for (let i = 0; i < contents.length; i++) {
    if (i % 5 === 0) await new Promise(r => setTimeout(r, 1)); // Yield more frequently to keep UI responsive
    const item = contents[i];
    const itemUri = `${dirUri}${dirUri.endsWith('/') ? '' : '/'}${item}`;
    const itemInfo = await FileSystem.getInfoAsync(itemUri);
    if (itemInfo.isDirectory) {
      const subResults = await walkDir(itemUri);
      results = results.concat(subResults);
    } else {
      results.push(itemUri);
    }
  }
  return results;
}

// Convert a unix timestamp (string/number) to EXIF date string (YYYY:MM:DD HH:MM:SS)
function getExifDateString(unixTimestampStr) {
  const ts = parseInt(unixTimestampStr, 10);
  if (isNaN(ts)) return null;
  const date = new Date(ts * 1000);

  const pad = (n) => n.toString().padStart(2, '0');
  const Y = date.getUTCFullYear();
  const M = pad(date.getUTCMonth() + 1);
  const D = pad(date.getUTCDate());
  const h = pad(date.getUTCHours());
  const m = pad(date.getUTCMinutes());
  const s = pad(date.getUTCSeconds());

  return `${Y}:${M}:${D} ${h}:${m}:${s}`;
}

// Match json file to a media file, accounting for Google Takeout truncations and extensions
function findCompanionMedia(jsonUri, mediaFilesSet) {
  // 1. Strip the .json suffix
  let base = jsonUri.replace(/\.json$/i, '');

  // 2. Strip supplemental metadata extensions (.suppleme or .supplemental-metadata)
  base = base.replace(/\.suppleme(ntal-metadata)?$/i, '');
  base = base.replace(/\.metadata$/i, '');

  // 3. Check exact match
  if (mediaFilesSet.has(base)) {
    return base;
  }

  // 4. Try appending common media extensions if Google Takeout stripped them in the JSON name
  const extensions = ['.jpg', '.jpeg', '.png', '.heic', '.webp', '.mp4', '.gif'];
  for (const ext of extensions) {
    if (mediaFilesSet.has(base + ext)) {
      return base + ext;
    }
    if (mediaFilesSet.has(base + ext.toUpperCase())) {
      return base + ext.toUpperCase();
    }
  }

  // 5. Handle Takeout's 46-character name truncation (e.g. longname_CO.json matching longname_COVER.jpg)
  const jsonFilename = jsonUri.split('/').pop().replace(/\.json$/i, '').replace(/\.suppleme(ntal-metadata)?$/i, '');
  const dirPath = jsonUri.substring(0, jsonUri.lastIndexOf('/') + 1);

  for (const mediaUri of mediaFilesSet) {
    if (mediaUri.startsWith(dirPath)) {
      const mediaFilename = mediaUri.substring(dirPath.length);
      // Check if media filename starts with the truncated JSON name
      if (mediaFilename.startsWith(jsonFilename) || jsonFilename.startsWith(mediaFilename.split('.')[0])) {
         return mediaUri;
      }
    }
  }

  return null;
}

export async function processExtractedFiles(extractedDirUri, addLog, setProgress, outputDirUri) {
  console.log(`[DEBUG] processExtractedFiles started on: ${extractedDirUri}`);
  addLog('Scanning directories for files...');
  const allFiles = await walkDir(extractedDirUri);
  console.log(`[DEBUG] walkDir finished. Total files found: ${allFiles.length}`);

  const jsonFiles = allFiles.filter(f => f.toLowerCase().endsWith('.json') && !f.includes('metadata.json'));
  const mediaFilesSet = new Set(allFiles.filter(f => !f.toLowerCase().endsWith('.json') && !f.toLowerCase().endsWith('.html')));

  console.log(`[DEBUG] JSON sidecars: ${jsonFiles.length}, Media files: ${mediaFilesSet.size}`);
  addLog(`Found ${jsonFiles.length} JSON sidecars and ${mediaFilesSet.size} media files.`);

  let successCount = 0;
  let failCount = 0;

  console.log(`[DEBUG] Starting JSON iteration...`);
  console.log(`[DEBUG] Sample JSON Files:`, jsonFiles.slice(0, 5));
  console.log(`[DEBUG] Sample Media Files:`, Array.from(mediaFilesSet).slice(0, 5));

  for (let i = 0; i < jsonFiles.length; i++) {
    if (i % 10 === 0) {
      setProgress(0.5 + (i / jsonFiles.length) * 0.3); // Scale metadata phase from 50% to 80%
      await new Promise(r => setTimeout(r, 10)); // Yield to UI thread
    }

    const jsonUri = jsonFiles[i];

    // Find companion media
    const companionUri = findCompanionMedia(jsonUri, mediaFilesSet);
    if (i < 5) {
      console.log(`[DEBUG] Matching Attempt ${i}:`);
      console.log(`  jsonUri: ${jsonUri}`);
      console.log(`  companionUri: ${companionUri}`);
      console.log(`  Match found: ${!!companionUri}`);
    }
    if (!companionUri) {
      continue;
    }

    // Process only JPEGs with piexifjs for now
    if (!companionUri.toLowerCase().endsWith('.jpg') && !companionUri.toLowerCase().endsWith('.jpeg')) {
      continue;
    }

    try {
      // Read JSON
      const jsonStr = await FileSystem.readAsStringAsync(jsonUri);
      const metadata = JSON.parse(jsonStr);

      const ts = metadata?.photoTakenTime?.timestamp;
      if (!ts) continue;

      const exifDate = getExifDateString(ts);
      if (!exifDate) continue;

      // Yield to UI before heavy Base64 and EXIF parsing
      setProgress(0.5 + (i / jsonFiles.length) * 0.5);
      await new Promise(r => setTimeout(r, 5));

      // Read JPEG as Base64 for piexif
      const base64Data = await FileSystem.readAsStringAsync(companionUri, { encoding: FileSystem.EncodingType.Base64 });
      const dataUrl = `data:image/jpeg;base64,${base64Data}`;

      // Load EXIF
      let exifObj;
      try {
        exifObj = piexif.load(dataUrl);
      } catch (e) {
        exifObj = { "0th": {}, "Exif": {}, "GPS": {} }; // Create empty if none
      }

      // Update tags
      exifObj["0th"][piexif.ImageIFD.DateTime] = exifDate;
      exifObj["Exif"][piexif.ExifIFD.DateTimeOriginal] = exifDate;
      exifObj["Exif"][piexif.ExifIFD.DateTimeDigitized] = exifDate;

      // Dump and insert
      const exifbytes = piexif.dump(exifObj);
      const newDataUrl = piexif.insert(exifbytes, dataUrl);

      // Yield to UI before heavy string split
      await new Promise(r => setTimeout(r, 5));

      // Save back (strip data:image/jpeg;base64,)
      const newBase64 = newDataUrl.split(',')[1];
      await FileSystem.writeAsStringAsync(companionUri, newBase64, { encoding: FileSystem.EncodingType.Base64 });

      successCount++;
    } catch (e) {
      failCount++;
      console.warn(`Failed to process ${companionUri}: ${e.message}`);
    }
  }

  if (outputDirUri) {
    console.log(`[DEBUG] Copying files to SAF directory: ${outputDirUri}`);
    addLog('Copying processed photos and videos to destination folder...');
    const mediaArray = Array.from(mediaFilesSet);
    for (let j = 0; j < mediaArray.length; j++) {
      if (j % 5 === 0) {
        setProgress(0.8 + (j / mediaArray.length) * 0.2); // Scale copying phase from 80% to 100%
        await new Promise(r => setTimeout(r, 10)); // Yield to UI
      }
      const localUri = mediaArray[j];
      try {
        const fileName = localUri.split('/').pop();
        let mimeType = 'image/jpeg';
        const lower = fileName.toLowerCase();
        if (lower.endsWith('.png')) mimeType = 'image/png';
        else if (lower.endsWith('.gif')) mimeType = 'image/gif';
        else if (lower.endsWith('.webp')) mimeType = 'image/webp';
        else if (lower.endsWith('.heic')) mimeType = 'image/heic';
        else if (lower.endsWith('.mp4')) mimeType = 'video/mp4';

        console.log(`[DEBUG] Creating SAF file for: ${fileName}`);
        const safFileUri = await FileSystem.StorageAccessFramework.createFileAsync(
          outputDirUri,
          fileName,
          mimeType
        );
        console.log(`[DEBUG] SAF file created at: ${safFileUri}`);

        try {
          // Try native copy first
          await FileSystem.copyAsync({
            from: localUri,
            to: safFileUri
          });
          console.log(`[DEBUG] Natively copied ${fileName} successfully`);
        } catch (err) {
          console.warn(`[DEBUG] Native copy failed, attempting base64 fallback for ${fileName}:`, err.message);
          const base64 = await FileSystem.readAsStringAsync(localUri, { encoding: FileSystem.EncodingType.Base64 });
          await FileSystem.StorageAccessFramework.writeAsStringAsync(
            safFileUri,
            base64,
            { encoding: FileSystem.EncodingType.Base64 }
          );
          console.log(`[DEBUG] Base64 fallback write succeeded for ${fileName}`);
        }
      } catch (copyErr) {
        console.error(`[DEBUG] Failed to copy ${localUri} to SAF:`, copyErr);
      }
    }
    addLog(`Successfully copied ${mediaArray.length} files to destination folder.`);
  }

  setProgress(1.0);
  addLog(`Completed! Updated EXIF for ${successCount} JPEG files. (${failCount} errors)`);
  return { successCount, failCount };
}
