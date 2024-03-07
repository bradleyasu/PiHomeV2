
sVINYL = '''
$HEADER$
#define BARS 12.

#define PI 3.14159265359

uniform vec2 resolution;
uniform float time;
uniform sampler2D iChannel0;
uniform sampler2D channel0;
uniform sampler2D texture1;
uniform sampler2D texture3;
uniform sampler2D audioTexture;
uniform float offsetX;
uniform float offsetY;

// rotation transform
void tRotate(inout vec2 p, float angel) {
    float s = sin(angel), c = cos(angel);
	p *= mat2(c, -s, s, c);
}

// circle distance
float sdCircle(vec2 p, float r) {
    return length(p) - r;
}

// union
float opU(float a, float b) {
    return min(a, b);
}

// substraction
float opS(float a, float b) {
    return max(a, -b);
}

// distance function of half of an ark
// parameters: inner radius, outer radius, angle
float sdArk(vec2 p, float ir, float or, float a) {
    
    // add outer circle
    float d = sdCircle(p, or);
        
    // substract inner circle
    d = opS(d, sdCircle(p, ir));
    
    // rotate with angle
    tRotate(p, -a * PI / 2.);
    
    // clip the top
    d = opS(d, -p.y);
    
    // add circle to the top
    d = opU(d, sdCircle(p - vec2((or + ir) / 2., 0.), (or - ir) / 2.));
    return d;
}

void main(void)
{


   vec4 frag_coord = frag_modelview_mat * gl_FragCoord;

    vec2 uv = frag_coord.xy / resolution.xy ;

    // correct aspect ratio
    uv.x *= resolution.x / resolution.y;
    uv.x -= .22;
    uv.y -= .5;

    // center
    uv -= .5;
    
    // Add Offsets
    uv.x -= offsetX;
    uv.y -= offsetY;


    // little white padding
    uv *= 2.05;
    // add circles
    float d = sdCircle(uv, 1.);
    d = opS(d, sdCircle(uv, .34));
    d = opU(d, sdCircle(uv, .04));

    // calculate position of the bars
    float barsStart = .37;
    float barsEnd = .94;
    float barId = floor((length(uv) -barsStart) / (barsEnd - barsStart) * BARS);

    // only go forward if we're in a bar
    if (barId >= 0. && barId < BARS) {
        
        float barWidth = (barsEnd - barsStart) / BARS;
        float barStart = barsStart + barWidth * (barId + .25);
        float barAngel = texture2D(texture1, vec2(1. - barId / BARS, .25)).x * .5;

        // add a little rotation to completely ruin the beautiful symmetry
        tRotate(uv, -barAngel * .2 * sin(barId + time));
        
        // mirror everything
    	uv = abs(uv);
        
        // add the bars
        d = opS(d, sdArk(uv, barStart, barStart + barWidth / 2., barAngel));
    }
    
    // use the slope to render the distance with antialiasing
    float w = min(fwidth(d), .01);

    vec4 final_color = vec4(vec3(smoothstep(-w, w, d)), 1.0);

    // replace the white in the final color with a transparent color
    //if (d > 0.0) {
    //    final_color = vec4(0., 0., 0., 0.);
    //}

	gl_FragColor =  final_color;

    //float value = texture2D(iChannel0, uv).r;
    //gl_FragColor = vec4(vec3(value), 1.0);
}
'''