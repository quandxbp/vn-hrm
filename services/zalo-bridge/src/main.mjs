import { Zalo, LoginQRCallbackEventType } from 'zca-js';
import { createBridge } from './server.mjs';

const options = { logging: false, checkUpdate: false, selfListen: false };
const bridge = createBridge({
    token: process.env.ZALO_BRIDGE_TOKEN,
    dataDir: process.env.DATA_DIR || '/data',
    connect: credentials => new Zalo(options).login(credentials),
    loginQR: emit => new Zalo(options).loginQR(undefined, event => {
        switch (event.type) {
            case LoginQRCallbackEventType.QRCodeGenerated:
                emit({ type: 'qr', image: event.data.image.replace(/^data:image\/\w+;base64,/, '') });
                break;
            case LoginQRCallbackEventType.QRCodeScanned:
                emit({ type: 'scanned', name: event.data.display_name });
                break;
            case LoginQRCallbackEventType.QRCodeExpired:
                event.actions.abort();
                break;
            case LoginQRCallbackEventType.GotLoginInfo:
                emit({ type: 'credentials', credentials: event.data });
                break;
        }
    }),
});
bridge.server.listen(3000, '0.0.0.0', () => console.log('Zalo bridge listening on port 3000'));
