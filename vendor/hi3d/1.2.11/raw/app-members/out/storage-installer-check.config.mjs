import base from '../electron-builder.config.mjs';
export default { ...base, directories: { ...base.directories, output: 'release/storage-installer-check' }, forceCodeSigning: false, win: { ...base.win, signAndEditExecutable: false } };
