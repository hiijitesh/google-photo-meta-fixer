import * as FileSystem from 'expo-file-system/legacy';
import piexif from 'piexifjs';

// Walk a directory recursively and return all files
async function walkDir(dirUri) {
  let results = [];
  const dirInfo = await FileSystem.getInfoAsync(dirUri);
  if (!dirInfo.isDirectory) {
    return [dirUri];
  }

  const contents = await FileSystem.readDirectoryAsync(dirUri);
  for (let i = 0; i < contents.length; i++) {
    if (i % 20 === 0) await new Promise(r => setTimeout(r, 10)); // Yield to UI
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

// Match json file to a media file
function findCompanionMedia(jsonUri, allFiles) {
  // Google Takeout usually appends .json to the filename, e.g., image.jpg.json or image.json
  const base1 = jsonUri.replace(/\\.json$/i, ''); // image.jpg
  let base2 = jsonUri.replace(/\\.[^.]+\\.json$/i, ''); // maybe handles image.jpg.json -> image if extensions are stripped

  // Exact match
  if (allFiles.includes(base1) && !base1.endsWith('/')) {
    return base1;
  }

  // Sometimes Takeout truncates extensions or adds (1)
  const filenameWithoutJson = jsonUri.split('/').pop().replace(/\\.json$/i, '');
  // Simplified matching for MVP: just try removing .json
  return null;
}

export async function processExtractedFiles(extractedDirUri, addLog, setProgress) {
  addLog('Scanning directories for files...');
  const allFiles = await walkDir(extractedDirUri);

  const jsonFiles = allFiles.filter(f => f.toLowerCase().endsWith('.json') && !f.includes('metadata.json'));
  const mediaFilesSet = new Set(allFiles.filter(f => !f.toLowerCase().endsWith('.json') && !f.toLowerCase().endsWith('.html')));

  addLog(`Found ${jsonFiles.length} JSON sidecars and ${mediaFilesSet.size} media files.`);

  let successCount = 0;
  let failCount = 0;

  for (let i = 0; i < jsonFiles.length; i++) {
    if (i % 10 === 0) {
      setProgress(0.5 + (i / jsonFiles.length) * 0.5); // Second half of progress bar
      await new Promise(r => setTimeout(r, 10)); // Yield to UI thread
    }

    const jsonUri = jsonFiles[i];

    // Find companion media
    const companionUri = jsonUri.replace(/\.json$/i, '');
    if (!mediaFilesSet.has(companionUri)) {
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

  setProgress(1.0);
  addLog(`Completed! Updated EXIF for ${successCount} JPEG files. (${failCount} errors)`);
  return { successCount, failCount };
}
