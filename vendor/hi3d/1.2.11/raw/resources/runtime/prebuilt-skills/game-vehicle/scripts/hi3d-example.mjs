import * as m from './hi3d-core.mjs';
console.log(m.drive({x:0,z:0,heading:0,speed:0},{throttle:1,steer:0},.1,{wheelbase:2,maxSpeed:20,acceleration:5,drag:.1,maxSteer:.5}));
